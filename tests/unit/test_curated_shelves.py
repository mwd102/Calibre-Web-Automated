"""Award matching and archive scope regressions."""
import json
from datetime import date, timedelta

import pytest
from cps import curated_shelves as curated


def test_title_and_author_are_required_and_subtitles_are_accepted():
    assert curated.matching_records('James: A Novel', ['Percival Everett'], 'pulitzer')
    assert not curated.matching_records('James', ['Henry James'], 'pulitzer')
    assert not curated.matching_records('James 2', ['Percival Everett'], 'pulitzer')
    assert curated.matching_records('James', ['Everett|Percival'], 'pulitzer')


def test_joint_winners_and_multiple_categories_survive():
    winners = [r for r in curated.catalog('pulitzer')['records'] if r['year'] == 2023 and r['category'] == 'Fiction']
    assert {r['title'] for r in winners} == {'Trust', 'Demon Copperhead'}
    assert {b['category'] for b in curated.badges('Onyx Storm', ['Rebecca Yarros'], 'goodreads', 2025)} == {'Audiobook', 'Romantasy'}


def test_year_filter_and_best_recorded_rank():
    records = curated.matching_records('The Women', ['Kristin Hannah'], 'nyt', 2024)
    assert records and min(r['rank'] for r in records) == 1
    badges = curated.badges('The Women', ['Kristin Hannah'], 'nyt', 2024)
    assert next(b for b in badges if b['category'] == 'Fiction')['label'] == 'NYT · Best recorded #1'
    assert all(b['year'] == 2024 for b in badges)
    assert any(r['rank'] > 1 for r in curated.catalog('nyt')['records'])
    assert all(1 <= r['rank'] <= 25 for r in curated.catalog('nyt')['records'])
    assert sum(c['rejected_rows'] for c in curated.catalog('nyt')['coverage']) == 154


def test_archive_dates_are_honest_and_award_years_complete():
    coverage = curated.catalog('nyt')['coverage']
    for row in coverage:
        assert row['weeks'] + len(row['missing_dates']) == row['expected_weeks']
    assert next(c for c in coverage if c['year'] == 2023)['missing_dates'] == ['2023-01-15']
    assert next(c for c in coverage if c['year'] == 2024)['last_date'] == '2024-12-01'
    assert {r['year'] for r in curated.catalog('goodreads')['records']} == set(range(2015, 2026))
    records = curated.catalog('pulitzer')['records']
    fiction = [r for r in records if r['category'] == 'Fiction']
    nonfiction = [r for r in records if r['category'] == 'General Nonfiction']
    assert len(fiction) == 100
    assert len(nonfiction) == 69
    assert {r['year'] for r in fiction} == set(range(1918, 2027)) - {1920, 1941, 1946, 1954, 1957, 1964, 1971, 1974, 1977, 2012}
    assert {r['year'] for r in nonfiction} == set(range(1962, 2027))
    assert all(r['authors'] and r['title'] for k in curated.COLLECTIONS for r in curated.catalog(k)['records'])


@pytest.mark.parametrize('value', ['2014', '9999', 'oops', '-1'])
def test_invalid_year_rejected(value):
    with pytest.raises(ValueError):
        curated.selected_year(value, 'nyt')


def test_unknown_collection_cannot_read_files():
    with pytest.raises(KeyError):
        curated.catalog('../config')


@pytest.mark.parametrize('collection, year', [('pulitzer', 2025), ('nyt', 2024)])
def test_library_matching_obeys_visibility_and_sees_new_books(monkeypatch, collection, year):
    from sqlalchemy import Column, Integer, String, Table, ForeignKey, create_engine
    from sqlalchemy.orm import declarative_base, Session
    from types import SimpleNamespace
    from cps import db
    base = declarative_base()

    class Book(base):
        __tablename__ = 'books'
        id = Column(Integer, primary_key=True)
        title = Column(String)

    class Author(base):
        __tablename__ = 'authors'
        id = Column(Integer, primary_key=True)
        name = Column(String)

    class Identifier(base):
        __tablename__ = 'identifiers'
        id = Column(Integer, primary_key=True)
        book = Column(Integer, ForeignKey('books.id'))
        type = Column(String)
        val = Column(String)

    link = Table('books_authors_link', base.metadata,
                 Column('book', ForeignKey('books.id')), Column('author', ForeignKey('authors.id')))
    engine = create_engine('sqlite://')
    base.metadata.create_all(engine)
    monkeypatch.setattr(db, 'Books', Book)
    monkeypatch.setattr(db, 'Authors', Author)
    monkeypatch.setattr(db, 'Identifiers', Identifier)
    monkeypatch.setattr(db, 'books_authors_link', link)
    with Session(engine) as session:
        session.add_all([Book(id=1, title='James'), Book(id=2, title='James'),
                         Author(id=1, name='Percival Everett')])
        session.flush()
        session.execute(link.insert(), [{'book': 1, 'author': 1}, {'book': 2, 'author': 1}])
        cdb = SimpleNamespace(session=session, common_filters=lambda: Book.id != 2)
        assert set(curated.library_matches(cdb, collection, year)) == {1}
        session.add(Book(id=3, title='James: A Novel'))
        session.flush()
        session.execute(link.insert(), [{'book': 3, 'author': 1}])
        assert set(curated.library_matches(cdb, collection, year)) == {1, 3}
    engine.dispose()


def test_nyt_api_date_validation_and_all_ranked_entries():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location('nyt_sync', Path(__file__).resolve().parents[2] / 'scripts/sync_nyt_catalog.py')
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    payload = {'results': {'published_date': '2025-01-05', 'lists': [
        {'list_name': 'Hardcover Fiction', 'list_name_encoded': 'hardcover-fiction', 'books': [
            {'title': 'First', 'author': 'Author One', 'rank': 1},
            {'title': 'Fifteenth', 'author': 'Author Two', 'rank': 15},
            {'title': 'Unknown Author', 'author': '', 'rank': 8},
        ]}]}}
    snapshot = sync.extract_snapshot(payload, '2025-01-05')
    assert json.loads(sync.serialize_snapshots({'snapshots': [snapshot]})) == {'snapshots': [snapshot]}
    assert [r['rank'] for r in snapshot['records']] == [1, 15, 8]
    assert all(r['category'] == 'Hardcover Fiction' for r in snapshot['records'])
    assert all('api-key' not in r['source'] for r in snapshot['records'])
    with pytest.raises(ValueError):
        sync.extract_snapshot(payload, '2025-01-12')


def test_nyt_transport_errors_do_not_expose_request_urls(monkeypatch):
    import importlib.util
    from pathlib import Path
    import urllib.error
    spec = importlib.util.spec_from_file_location('nyt_sync_redaction', Path(__file__).resolve().parents[2] / 'scripts/sync_nyt_catalog.py')
    sync = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sync)
    def fail(*args, **kwargs):
        raise urllib.error.HTTPError('https://example.test/?api-key=private', 429, 'private', {}, None)
    monkeypatch.setattr(sync.urllib.request, 'urlopen', fail)
    with pytest.raises(RuntimeError) as error:
        sync.request('https://example.test/?api-key=private')
    assert str(error.value) == 'HTTP 429'


def test_missing_source_author_needs_matching_isbn_and_title(monkeypatch):
    record = {'title': 'The Book of Bill', 'authors': [''], 'year': 2024,
              'category': 'Advice', 'rank': 5, 'isbn': '9781368092203'}
    monkeypatch.setattr(curated, 'record_index', lambda key: {curated.title_key(record['title']): [record]})
    assert not curated.matching_records('The Book of Bill', [''], 'nyt')
    assert not curated.matching_records('The Book of Bill', ['Alex Hirsch'], 'nyt', isbns=['0000000000000'])
    assert curated.matching_records('The Book of Bill', ['Alex Hirsch'], 'nyt', isbns=['978-1-368-09220-3'])
    assert not curated.matching_records('Different Book', ['Alex Hirsch'], 'nyt', isbns=['9781368092203'])


def test_named_coauthor_can_match_without_fuzzy_surnames(monkeypatch):
    record = {'title': 'Collaboration', 'authors': ['Douglas Preston and Lincoln Child'], 'year': 2024}
    monkeypatch.setattr(curated, 'record_index', lambda key: {'collaboration': [record]})
    assert curated.matching_records('Collaboration', ['Lincoln Child'], 'nyt')
    assert not curated.matching_records('Collaboration', ['Julia Child'], 'nyt')


def test_weekly_coverage_denominator_counts_all_sundays():
    assert len(curated.weekly_dates(2023)) == 53
    assert len(curated.weekly_dates(2025)) == 52


def test_rank_badge_links_to_the_best_recorded_week(monkeypatch):
    base = {'title': 'Collaboration', 'authors': ['Douglas Preston'], 'year': 2024, 'category': 'Hardcover Fiction'}
    records = [dict(base, rank=12, source='https://example.test/week-one'),
               dict(base, rank=2, source='https://example.test/week-two')]
    monkeypatch.setattr(curated, 'record_index', lambda key: {'collaboration': records})
    badge = curated.badges('Collaboration', ['Douglas Preston'], 'nyt')[0]
    assert badge['label'] == 'NYT · Best recorded #2'
    assert badge['source'] == 'https://example.test/week-two'


def test_all_time_pulitzer_filter_and_first_winners():
    assert curated.selected_year('1918', 'pulitzer') == 1918
    assert curated.selected_year('all', 'pulitzer') is None
    with pytest.raises(ValueError):
        curated.selected_year('1917', 'pulitzer')
    with pytest.raises(ValueError):
        curated.selected_year('1918', 'goodreads')
    first = curated.matching_records('His Family', ['Ernest Poole'], 'pulitzer', 1918)
    assert first[0]['original_category'] == 'Novel'
    assert curated.matching_records('The Making of the President 1960', ['Theodore H. White'], 'pulitzer', 1962)
    assert curated.matching_records('To Kill a Mockingbird', ['Harper Lee'], 'pulitzer', 1961)
    assert not curated.matching_records('The Pale King', ['David Foster Wallace'], 'pulitzer', 2012)
    for year in (1969, 1973, 1986, 2020):
        assert len([r for r in curated.catalog('pulitzer')['records']
                    if r['year'] == year and r['category'] == 'General Nonfiction']) == 2
