# Hyperion production replacement readiness

**Completed on 2026-09-13.** Hyperion now runs the released fork with its existing
accounts, split library and Kobo identity. A final off-site state backup was
restored and verified, and the book tree was cloned with writers stopped. The
production deployment disables CWA background automation and preserves the
Calibre-Web trusted-proxy/shared-secret boundary. See the
[canonical production and rollback record](https://github.com/mwd102/Hyperion/blob/main/docs/books-migration.md#hyperion-cwa-cutover--2026-09-13)
and [published release](https://github.com/mwd102/Calibre-Web-Automated/releases/tag/hyperion-2026.09.13.1).

The assessment below is the historical pre-cutover checklist. Its blockers were
resolved in the canonical production record; it is retained as migration context.

Original assessment: **not ready for an image-only production swap**. This is a preparation
record, not a deployable production manifest or authorization to cut over.
Observations were verified on 2026-09-13; repeat them before release.

## Verified baseline

* Hyperion's `books` Argo CD application is Synced/Healthy at
  `2e17073da53675908f3f53ec901b8685066acb62`, matching reachable `origin/main`.
  Authoritative declarations: `clusters/hyperion/workloads/books/` in
  [Hyperion](https://github.com/mwd102/Hyperion/tree/2e17073da53675908f3f53ec901b8685066acb62/clusters/hyperion/workloads/books).
  The local Hyperion checkout was behind/divergent; it was not used as final
  desired-state proof and was not modified.
* Live web image is LinuxServer Calibre-Web 0.6.27,
  `sha256:1870b57874a831d7c0c389547826e5be38089c437276299e1646b7c81a497347`.
  One Recreate deployment also contains Calibre Content Server (CCS), an EPUB
  importer that writes through CCS, and a SQLite snapshot sidecar.
* Live config is `/config/app.db`, with its existing `/config/.key`.
  Library metadata is `/library/metadata.db`; split-library settings point book
  files to `/books`. Both SQLite databases passed `PRAGMA quick_check`.
  Counts: 5,618 books, 7 user rows, 5 shelves, 1 remote-auth-token row and
  5 Kobo-synced-book rows. Counts are checkpoints, not identity-equivalence proof.
* `books-state` is a 256 MiB Longhorn claim, healthy, with approximately 21 MiB
  filesystem usage and 198 MiB available at inspection. Its nightly-backup
  label is enabled, but `status.lastBackup` and `status.lastBackupAt` are empty;
  no matching BackupVolume was visible. **A completed backup/restore has not
  been established.** Existing historical app.db copies are not a full restore
  rehearsal and do not establish a backup of current metadata or book files.
* CWA dev runs source `540fd035cb9e428648ed898d3656310ca088ecd1`, image
  `sha256:421cb724aeee813301e21b9c1817595ae89bf1bc565fa16f44082f56f6925973`.
  It has isolated state, a metadata copy and an empty ingest directory. It does
  not contain the full live book/cover tree or reproduce production's topology.
* Dev's memory limit is 3 GiB after earlier OOMs at 2 GiB; inspection observed
  approximately 1.2 GiB usage. Live web is limited to 512 MiB. This is a sizing
  and soak-test requirement, not proof that increasing the limit fixes growth.
* PRs #7–#18 form an unmerged feature stack. Their latest image is a UAT build,
  not an integrated release from main. GHCR UAT builds and CI unit/browser/policy
  checks pass. The independent default registry workflow still fails its login.

## Required preparation

### 1. Prove backup and rollback

- [ ] Investigate the missing Books backup record; create and verify a fresh
  backup in the designated durable backup system.
- [ ] Restore into isolated storage and verify SQLite integrity, user IDs,
  password hashes, shelves, book IDs/UUIDs, reading state, Kobo tokens and
  encrypted configuration. Compare credentials only in protected process
  memory; never print them or store them in this repository.
- [ ] Preserve the matching encryption key and config tree, CCS user database,
  metadata database and the book-tree recovery path. A catalogue snapshot alone
  is not a backup of the books and application state.
- [ ] Rehearse running the old image on the restored pre-upgrade state. Do not
  assume old Calibre-Web can read databases after CWA migrations.
- [ ] Define the rollback write cutoff: reverting databases loses post-cutover
  changes unless they are captured/reconciled. Stop new writers before restoring
  old state and restarting the old stack.

### 2. Resolve the library-writer and path contract

Hyperion's `docs/books-migration.md` assigns CCS sole library-writer ownership.
CWA introduces ingestion, conversions, metadata updates and checksum/schema
maintenance. Keeping both stacks at their defaults is not a reviewed contract.

- [ ] First rehearse retaining CCS/importer ownership and explicitly disabling
  or adapting every CWA library-writing service/action. If full CWA ownership
  is preferred, prepare an explicit importer/CCS ownership handoff instead.
  Keep the established content endpoint's consumers working in either design.
- [ ] Preserve `/library` + `/books` split settings and prove book downloads,
  cover reads, edits/conversions and imports use the correct paths.
- [ ] Set `DISABLE_LIBRARY_AUTOMOUNT=true` when preserving the existing library
  settings. `cwa-auto-library` otherwise scans `/calibre-library` and can create
  a new library or reset its location. This flag disables auto-library only;
  it does **not** disable all writers.
- [ ] Audit `cwa-init`, `cwa-ingest-service`, `cwa-checksum-backfill`, metadata
  monitoring, scheduler jobs and web write actions. For example, checksum
  backfill hardcodes `/calibre-library/metadata.db`, while web DB setup uses
  `config_calibre_dir`. An empty ingest directory prevents ordinary incoming
  imports but does not prove all background writes are disabled.
- [ ] Prevent recursive ownership changes over the live shared book tree and
  preserve UID/GID 99:100. Account for CWA's processed-file backups/cache growth
  outside the small authoritative state claim.

### 3. Rehearse with production-shaped isolated data

- [ ] Use a fresh protected live-state backup, with isolated writable metadata
  and representative copied EPUBs/KEPUBs/covers. Do not attach a second writable
  application to live storage. Do not restore dev's test credentials/settings
  into production.
- [ ] Compare retained identities and configuration before/after first start
  and a subsequent restart. Keep book IDs/UUIDs and Amy's existing token intact
  so her device endpoint does not need replacing.
- [ ] Check actual downloads, conversions/imports according to the chosen
  writer contract, OPDS, email recipient selection, mobile book/profile/admin
  pages, existing shelves, reading progress and new-library matching.
- [ ] Test fresh login and existing-account mapping through Oathkeeper/Access,
  including trusted-header rejection from untrusted clients. Preserve the
  reverse-proxy secret and trusted-proxy boundary.
- [ ] Validate Kobo through the real route and its store-proxy path. Dev's proxy
  is disabled; production's is enabled with a `storeapi.kobo.com` host alias.
  Existing simulated sync proves the new shelf membership works, not the
  production networking path or a physical device download.
- [ ] Arrange an actual Kobo sync/download acceptance check with Amy after the
  approved cutover. Do not silently enqueue live books as a test.

### 4. Release and operational readiness

- [ ] Integrate the feature stack into main in dependency order and validate
  that exact combined commit. Publish a versioned amd64 GHCR release with source
  provenance and an immutable digest; Hyperion nodes are amd64.
- [ ] Choose/document the production registry workflow and remove or repair
  the failing unrelated registry jobs. Confirm production pull-secret access
  using the established Infisical projection, without copying secret values.
- [ ] Size memory/CPU from a production-shaped soak test. Exercise repeated
  browsing, award shelves, Kobo sync and background work, and observe memory
  after idle periods and restart. Preserve node headroom and resource alerts.
- [ ] Add a suitable startup probe and validate readiness/liveness behavior
  through migrations and restart. Budget app-state growth and verify storage
  alerts and backup monitoring actually fire on the relevant conditions.
- [ ] Decide how existing users opt into Pastel. Live's global theme is Standard;
  a new image alone is not proof every retained user will see Pastel.
- [ ] Document manual award/NYT catalog refreshes and their remaining historical
  coverage gaps; there is currently no automatic refresh job.

## Concrete production change boundary

Prepare the eventual deployment PR in **Hyperion**, under
`clusters/hyperion/workloads/books/`, against freshly fetched main and its scoped
governance. Preserve Argo CD ownership; do not apply the dev manifest to `books`.
The production PR must contain the chosen writer/path design, release digest,
pull-secret reference, resources, startup probes and any approved state-capacity
changes. Preserve these client identities/routes:

| Client | Retained endpoint |
| --- | --- |
| Browser / Access + Oathkeeper | `books.mwd.lol` |
| Kobo | `kobo.mwd.lol/kobo/*` only |
| Private web / OPDS | `books.tailcff11.ts.net:8083` |
| Calibre Content Server | `books-content.tailcff11.ts.net:8080` |

The existing `configure-trusted-proxy` init container also uses the old web
image; review its compatibility explicitly. Do not replace the other three
containers merely because the web image changes.

## Cutover gate

Only after the checks above: agree a short maintenance window, freeze writes
through the authoritative Git/controller workflow, take the final consistent
backup, start the release, verify clients and restart recovery, and retain the
stopped/restorable pre-upgrade state until acceptance. Preserve the source data
at the final checkpoint; the dev catalogue has already fallen behind live.

This assessment changed no production deployment, route, credentials, data or
backup schedule. No restore rehearsal or production device acceptance is claimed.
