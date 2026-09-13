# Curated shelf catalog

Factual title/author, award category, year and rank data only. No cover images,
reviews, descriptions or publisher citations are copied. Snapshot: 2026-09-13.
These virtual Magic Shelves do not modify Calibre metadata or user-created rules.

* Pulitzer: official [Fiction](https://www.pulitzer.org/prize-winners-by-category/219)
  and [General Nonfiction](https://www.pulitzer.org/prize-winners-by-category/223),
  all years through 2026: 100 Fiction winners including the former
  [Novel](https://www.pulitzer.org/prize-winners-by-category/261) prize (1918–1947),
  and 69 General Nonfiction winners (1962 onward), including joint winners.
  Novel entries retain their original category in the catalog and display as Fiction.
  Fiction/Novel had no winner in 1920, 1941, 1946, 1954, 1957, 1964, 1971, 1974,
  1977 and 2012; these are not missing data. Short titles are used where
  editions have differing subtitles.
* Goodreads: Kris Bruurs' [2011–2024 public archive](https://www.kaggle.com/datasets/krisbruurs/goodreads-choice-awards-2011-2024-books),
  offered under CC0. Select the highest vote count per award year/category,
  2015–2024 (185 winners; includes 2018's special Best of the Best).
  2025's 15 winners are transcribed from the [official announcement](https://www.goodreads.com/blog/show/3030-meet-the-winners-of-the-2025-goodreads-choice-awards).
  2015 winners were cross-checked against the official year page. Historical
  archive vote counts are not independently verified for every category.
* NYT: Bryant Reese's [1931–2024 public archive](https://www.kaggle.com/datasets/bryantreese/nyt-bestsellers-1931-2024-fictionnon-fiction),
  offered under MIT. 15,717 raw weekly entries from 2015 onward become 3,805
  year/category/title/author records after excluding 154 malformed rows with
  missing authors or implausible ranks (outside 1–25). Exclusion counts remain
  visible per year/category. Parenthetical publisher/description artifacts in
  author fields are removed before matching. Each retains minimum observed rank and
  first/last recorded list dates. No rank threshold excludes lower-ranked books.
  The archive does not identify list format; it cannot establish coverage of all
  NYT lists (including paperback, children's and specialist lists).
  2023-01-15 is missing for both categories. 2024 ends at the list date 2024-12-01;
  four December Sundays are absent. 2025 onward has no records.
  Earlier years contain every Sunday date, which does **not** prove every ranked
  entry is present or accurate. Badges always say **best recorded**, not an
  independently verified lifetime or full-year peak.

## Rebuild

Download the public archive ZIPs via their source pages. Run:

```sh
python3 scripts/import_curated_archives.py --nyt /path/nyt.zip --goodreads /path/goodreads.zip
```

Pulitzer is maintained independently in `pulitzer.json` against the three official
category archives above; this rebuild leaves it unchanged. Include winner headings
only, preserve joint winners, and do not import finalists or empty award years.

This script uses only the standard library and local files. It never fetches data
at application startup. Review source changes and coverage before committing a
new snapshot. Archive hashes used for this snapshot:

* NYT SHA256: `e1b62039700408d4e71ad8db510bf7c2483d0ec74239c506c21c0aadbd8855c7`
* Goodreads SHA256: `b81a500189979a260172ccd578f44fe64d3b9bbf1eac0527a9ca830acb83d815`

## Matching and privacy

Matches require normalized title plus a full author name or an exact API ISBN,
with subtitle and numbered series suffix tolerance. There is no fuzzy or title-only matching.
Alternate translated titles and inconsistent author initials can remain unmatched.
New library books are matched on the next shelf request; unmatched source records
remain bundled. Current-user visibility filters apply before matching and again
before book retrieval. Results and counts are not shared between users.

## NYT API supplementation

The user subsequently supplied API access. `nyt_api.json` stores only factual
snapshots from `/svc/books/v3/lists/full-overview.json`, across **all lists
returned** (including paperback, children’s, audio and specialist lists).
Each snapshot must match the requested publication date. Missing author names
are retained; an exact ISBN plus title can still match them. API list names remain separate from the
public archive's unspecified-format Fiction/Non-fiction categories; ranks are
never combined across different lists. Individual badges link to the dated list.

Run `python3 scripts/sync_nyt_catalog.py` on shell-01 to resume the bounded import.
The default is 40 requests, separated by 12.5 seconds; HTTP errors stop the run
without claiming coverage for the failed date. Existing dates are skipped.
Review the generated diff, run tests, and deploy a new snapshot to update the app.
The first priorities are the current week and known public archive date gaps,
followed by earlier weeks back to 2015. This is a resumable snapshot importer,
not an automatically scheduled job. The UI lists the exact API dates available;
it does not claim the API backfill is complete.

Authentication is read-only from Infisical project
`b35a6135-d162-4234-bf83-97472191283c`, environment `dev`, path
`/NEW_YORK_TIMES_BOOKS`, key `KEY`. The unrelated `SECRET` key is not needed.
The importer uses the existing protected shell-01 Universal Auth files under
`~/.config/hyperion/infisical`, validates 0600 modes, and retains all credentials
only in process memory. No credential is projected into the application or
stored in snapshots, URLs in logs, Git, or ordinary temporary files. Transport
failures expose only HTTP status. Rotate in Infisical; the next import reads the
replacement. No credential copy or rotation was performed for this feature.

The initial API snapshot contains all 52 weekly dates in 2025 and all 37
weekly dates in 2026 through September 13, plus the five missing public-archive
dates (2023-01-15 and the last four Sundays of 2024). There are 94 verified
weekly snapshots in total. Earlier public-archive list/entry limitations remain
visible; complete dated API coverage before 2025 is not claimed.
