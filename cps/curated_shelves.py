"""Bundled, source-attributed award lists matched without changing library metadata."""
import json
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path

COLLECTIONS = {'pulitzer': 'Pulitzer Winners', 'goodreads': 'Goodreads Choice', 'nyt': 'NYT Bestsellers'}


def normalize(value):
    value = unicodedata.normalize('NFKD', value).casefold()
    return ''.join(c for c in value if c.isalnum() and not unicodedata.combining(c))


def title_key(value):
    # Editions often add a subtitle or Goodreads series suffix. Author matching
    # remains mandatory; numbers in titles are retained (e.g. Saga volumes).
    value = re.sub(r'\s+\([^)]*(?:#\d|series)[^)]*\)\s*$', '', value, flags=re.I)
    return normalize(value.split(':', 1)[0])


def author_keys(value):
    # Calibre sometimes stores surname|given name. Compare full name tokens,
    # never surname alone, so an identically titled book by someone else stays out.
    value = value.replace('|', ' ').replace(',', ' ')
    return ''.join(sorted(normalize(part) for part in value.split()))


def author_variants(value):
    names = [value] + re.split(r'\s+(?:and|with)\s+', value, flags=re.I)
    return {author_keys(name) for name in names if name.strip()}


def weekly_dates(year):
    start = date(year, 1, 1)
    end = min(date(year, 12, 31), datetime.now(timezone.utc).date())
    return [start + timedelta(days=i) for i in range((end - start).days + 1)
            if (start + timedelta(days=i)).weekday() == 6]


@lru_cache(maxsize=3)
def catalog(collection):
    if collection not in COLLECTIONS:
        raise KeyError(collection)
    root = Path(__file__).parent / 'data' / 'curated'
    data = json.loads((root / (collection + '.json')).read_text(encoding='utf-8'))
    if collection == 'nyt' and (root / 'nyt_api.json').exists():
        api = json.loads((root / 'nyt_api.json').read_text(encoding='utf-8'))
        grouped = {}
        coverage = defaultdict(list)
        for snapshot in api['snapshots']:
            coverage[int(snapshot['date'][:4])].append(snapshot['date'])
            for record in snapshot['records']:
                identity = (record['year'], record['category'], title_key(record['title']),
                            tuple(author_keys(a) for a in record['authors']))
                previous = grouped.get(identity)
                if previous is None or record['rank'] < previous['rank']:
                    grouped[identity] = dict(record)
        data['records'].extend(grouped.values())
        data['api_coverage'] = [{'year': year, 'dates': sorted(set(dates)),
                                 'expected_weeks': len(weekly_dates(year))}
                                for year, dates in sorted(coverage.items(), reverse=True)]
        data['api_updated'] = api['updated']
    return data


@lru_cache(maxsize=3)
def record_index(collection):
    index = defaultdict(list)
    for record in catalog(collection)['records']:
        index[title_key(record['title'])].append(record)
    return index


def matching_records(title, authors, collection, year=None, isbns=()):
    keys = set().union(*(author_variants(a) for a in authors))
    isbn_keys = {normalize(i) for i in isbns if i}
    return [r for r in record_index(collection).get(title_key(title), [])
            if (year is None or r['year'] == year)
            and (keys.intersection(set().union(*(author_variants(a) for a in r['authors'])))
                 or (r.get('isbn') and normalize(r['isbn']) in isbn_keys))]


def badges(title, authors, collection=None, year=None, isbns=()):
    result = []
    seen = set()
    for key in ([collection] if collection else COLLECTIONS):
        for record in matching_records(title, authors, key, year, isbns):
            identity = (key, record['year'], record['category'])
            if identity in seen:
                continue
            seen.add(identity)
            rank = None
            if key == 'nyt':
                record = min((r for r in matching_records(title, authors, key, record['year'], isbns)
                              if r['category'] == record['category']), key=lambda r: r['rank'])
                rank = record['rank']
            label = ('NYT · Best recorded #%s' % rank) if rank else ('Pulitzer' if key == 'pulitzer' else 'Goodreads winner')
            result.append(dict(collection=key, year=record['year'], category=record['category'],
                               label=label, source=record.get('source', catalog(key)['source'])))
    return sorted(result, key=lambda b: (-b['year'], b['collection'], b['category']))


def selected_year(raw, collection):
    if raw in (None, '', 'all'):
        return None
    year = int(raw)
    if not 2015 <= year <= datetime.now(timezone.utc).date().year:
        raise ValueError('Invalid collection year')
    return year


def library_matches(cdb, collection, year):
    """Read lightweight rows under current-user filters; no shared user cache."""
    from . import db
    rows = (cdb.session.query(db.Books.id, db.Books.title, db.Authors.name)
            .select_from(db.Books).join(db.books_authors_link).join(db.Authors)
            .filter(cdb.common_filters()).all())
    titles, authors = {}, defaultdict(list)
    for book_id, title, author in rows:
        titles[book_id] = title
        authors[book_id].append(author)
    isbns = defaultdict(list)
    if collection == 'nyt':
        identifier_rows = (cdb.session.query(db.Identifiers.book, db.Identifiers.val)
                           .join(db.Books, db.Books.id == db.Identifiers.book)
                           .filter(db.Identifiers.type == 'isbn', cdb.common_filters()).all())
        for book_id, value in identifier_rows:
            isbns[book_id].append(value)
    return {book_id: badges(title, authors[book_id], collection, year, isbns[book_id])
            for book_id, title in titles.items()
            if matching_records(title, authors[book_id], collection, year, isbns[book_id])}
