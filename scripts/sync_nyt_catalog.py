#!/usr/bin/env python3
"""Fetch factual NYT list snapshots with an Infisical key held only in memory.

No key, token, request URL, response body or exception text is logged. The app
reads the resulting catalog without receiving Infisical or NYT credentials.
"""
import argparse
from datetime import date, timedelta
import json
from pathlib import Path
import stat
import time
import urllib.error
import urllib.parse
import urllib.request

PROJECT = 'b35a6135-d162-4234-bf83-97472191283c'
SECRET_PATH = '/NEW_YORK_TIMES_BOOKS'


def request(url, body=None, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError('HTTP %s' % error.code) from None
    except Exception:
        raise RuntimeError('Request failed; sensitive details suppressed') from None


def read_key(credential_dir):
    for name in ('client-id', 'client-secret'):
        if stat.S_IMODE((credential_dir / name).stat().st_mode) != 0o600:
            raise RuntimeError('Infisical credential permissions must be 0600')
    auth = request('https://app.infisical.com/api/v1/auth/universal-auth/login', {
        'clientId': (credential_dir / 'client-id').read_text().strip(),
        'clientSecret': (credential_dir / 'client-secret').read_text().strip(),
    }, {'Content-Type': 'application/json'})
    query = urllib.parse.urlencode({'workspaceId': PROJECT, 'environment': 'dev',
                                   'secretPath': SECRET_PATH, 'type': 'shared'})
    payload = request('https://app.infisical.com/api/v3/secrets/raw/KEY?' + query,
                      headers={'Authorization': 'Bearer ' + auth['accessToken']})
    key = payload['secret']['secretValue'].strip()
    if not key:
        raise RuntimeError('NYT key is empty')
    return key


def extract_snapshot(payload, requested):
    result = payload['results']
    published = result['published_date']
    if published != requested:
        raise ValueError('API returned a different publication date')
    records = []
    lists = []
    for listing in result['lists']:
        name = listing['list_name']
        books = listing['books']
        lists.append({'name': name, 'entries': len(books)})
        for book in books:
            if not book['title'] or not isinstance(book['rank'], int) or book['rank'] < 1:
                raise ValueError('Invalid ranked entry')
            records.append({'year': int(published[:4]), 'category': name,
                            'title': book['title'], 'authors': [book['author']],
                            'rank': book['rank'], 'first_date': published, 'last_date': published,
                            'source': 'https://www.nytimes.com/books/best-sellers/' + published + '/' + listing['list_name_encoded'] + '/',
                            'isbn': book.get('primary_isbn13', '')})
    if payload.get('num_results', len(records)) != len(records):
        raise ValueError('API result count does not match ranked entries')
    if not records:
        raise ValueError('Empty list response')
    return {'date': published, 'lists': lists, 'records': records}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credential-dir', type=Path, default=Path.home() / '.config/hyperion/infisical')
    parser.add_argument('--max-requests', type=int, default=40)
    parser.add_argument('--interval', type=float, default=12.5)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'cps/data/curated/nyt_api.json')
    args = parser.parse_args()
    if args.max_requests < 1 or args.interval < 6:
        parser.error('Use a positive request budget and an interval of at least 6 seconds')
    key = read_key(args.credential_dir)
    saved = json.loads(args.output.read_text()) if args.output.exists() else {'snapshots': []}
    snapshots = {s['date']: s for s in saved['snapshots']}
    latest = date.today() + timedelta(days=(6 - date.today().weekday()) % 7)
    # Fill known holes first, then work backwards. Existing weeks are resumable.
    priority = [latest] + [date(2024, 12, d) for d in (8, 15, 22, 29)] + [date(2023, 1, 15)]
    days = priority + [latest - timedelta(weeks=i) for i in range((latest - date(2015, 1, 4)).days // 7 + 1)]
    attempted = set()
    count = 0
    for day in days:
        stamp = day.isoformat()
        if stamp in snapshots or stamp in attempted:
            continue
        attempted.add(stamp)
        query = urllib.parse.urlencode({'api-key': key, 'published_date': stamp})
        try:
            payload = request('https://api.nytimes.com/svc/books/v3/lists/full-overview.json?' + query)
            snapshots[stamp] = extract_snapshot(payload, stamp)
        except (RuntimeError, ValueError, KeyError) as error:
            # Do not log exception details: transports may contain authenticated URLs.
            reason = str(error) if isinstance(error, RuntimeError) else 'Response validation failed'
            print('NYT request stopped at %s (%s); saved coverage is unchanged for this date.' % (stamp, reason), flush=True)
            break
        saved = {'source': 'https://developer.nytimes.com/docs/books-product/1/overview',
                 'updated': date.today().isoformat(), 'snapshots': sorted(snapshots.values(), key=lambda s: s['date'])}
        temporary = args.output.with_suffix('.json.new')
        temporary.write_text(json.dumps(saved, ensure_ascii=False, indent=2) + '\n')
        temporary.replace(args.output)
        count += 1
        print('Saved NYT %s: %s lists, %s entries' % (stamp, len(snapshots[stamp]['lists']), len(snapshots[stamp]['records'])), flush=True)
        if count >= args.max_requests:
            break
        time.sleep(args.interval)
    print('Verified weekly API snapshots: %s' % len(snapshots), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('NYT sync failed; sensitive details suppressed') from None
