# Hyperion UAT copy

`devspace.yaml` deploys `books-cwa-dev` into the existing `books` namespace.
It has separate config and library claims, a disposable ingest directory, and
its own GHCR pull-secret projection. It does not mount the production Books
claim or publish a public route. DevSpace owns the resources labelled
`hyperion.mwd.lol/owner: manual`; Argo CD continues to own `books`.

Use the explicit shell-01 Hyperion kubeconfig and namespace:

The immutable amd64 UAT image is built by dispatching the existing
`Build & Push - Dev - Split Strategy` workflow with `uat_only=true` from the
selected branch. Pin the resulting image digest in `uat.yaml` before
deployment. DevSpace deploys the pinned image; a cold build is too large for
shell-01's local Docker disk.

```sh
devspace deploy --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig -n books
kubectl --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig -n books rollout status deployment/books-cwa-dev
```

For a local browser session, run `devspace dev` with the same flags. It forwards
port 8083. The fresh application's initial administrator login is documented in
the repository README; change that password on first login before inviting
other reviewers. No SMTP credentials or production book data are copied into
this instance by default. The later catalog-only import below copied production
book metadata, but not application users, credentials, covers, or book files.

The former private review route was
`https://shell-01.tailcff11.ts.net:18083/`. On shell-01, a persistent user
service forwarded local port 18083 to `svc/books-cwa-dev:8083`, and Tailscale
Serve published that port to the Tailnet. It had no Cloudflare or public
ingress. Check the forwarding service with
`systemctl --user status cwa-uat-portforward.service` and the Tailnet mapping
with `tailscale serve status`.

The initial review should cover login, selecting Standard and caliBlur themes,
search and book details in each theme, upload/ingest of a disposable book,
metadata editing, shelves, and the admin settings. Test Kobo, OAuth, LDAP,
mail delivery, and external metadata providers only after configuring separate
UAT credentials or fixtures for those paths.

The initial disposable TXT ingest succeeded and produced an EPUB in the UAT
library. KOReader checksum generation logged `no such table:
book_format_checksums` on this fresh install; investigate that separately
before accepting KOReader sync as tested.

## Real catalog review

`uat-catalog-import.yaml` is a one-time, manual Job. Production's Books pod
already creates an atomic SQLite backup of `metadata.db` every 60 seconds on
the `books-shared` JuiceFS claim. The Job mounts only that snapshot directory,
read-only, and copies a verified snapshot into the separate UAT library claim.
It never mounts the production `books-state` claim. CWA needs its own writable
catalog; a read-only SQLite file is not a supported full-function test target.

Stop UAT before the import, then check it has no running pods:

```sh
kubectl --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig -n books scale deployment/books-cwa-dev --replicas=0
kubectl --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig -n books rollout status deployment/books-cwa-dev
kubectl --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig -n books apply -f kubernetes/uat-catalog-import.yaml
kubectl --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig -n books wait --for=condition=complete job/books-cwa-dev-catalog-import-20260912-retry1 --timeout=180s
kubectl --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig -n books logs job/books-cwa-dev-catalog-import-20260912-retry1
kubectl --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig -n books scale deployment/books-cwa-dev --replicas=1
kubectl --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig -n books rollout status deployment/books-cwa-dev
```

The Job refuses a stale/missing source or an active UAT SQLite WAL. It retains the prior UAT catalog as
`metadata.db.uat-before-real-catalog-20260912` on the UAT library claim.
The first Job attempt failed on a JuiceFS SQLite backup read before replacing
the UAT catalog. This retry reads the production snapshot as an atomic file,
checks its SQLite integrity, and reuses the verified UAT backup.
On 2026-09-12, the retry completed with 5,608 imported entries, preserving the
original one-entry UAT catalog. SQLite `quick_check` passed on the UAT copy;
production and UAT deployments were both 1/1 ready, and the private review
route returned HTTP 302 to login. The first failed Job remains as an audit
record. Rollback is to stop UAT, restore the saved UAT catalog to
`metadata.db`, then restart UAT; production needs no rollback.
This is catalog-only: book files and covers are not cloned or mounted, so
downloads and file-based operations will not work for production entries.
The cover endpoint reads `cover.jpg` from each book's directory, so generic
cover placeholders are expected in this review.
Do not use destructive library actions while reviewing this catalog. UAT's
`app.db`, users, and credentials remain separate. Removing the Job after
verification does not remove either catalog; `devspace purge` does remove the
UAT claim, so retain the backup first if needed.

On 2026-09-12, the caliBlur book-action contrast fix was deployed from
`1ba1cec9d4899face27678dcf1c0b14596ca3460` using the pinned GHCR image
in `uat.yaml`. UAT rolled out 1/1 ready, retained 5,608 catalog entries, and
the private route redirected to login. Standard theme styles were unchanged;
the user still needs to visually accept the caliBlur icon fix.

`devspace purge` removes DevSpace-managed resources, including the UAT claims.
Export anything you want to retain before purging. Do not use it while UAT is
still in progress.

## UAT closeout (2026-09-12)

The owner accepted functional UAT with the limitation that this catalog-only
copy cannot prove cover, download, or browser-reader paths for production
books. The Tailnet Serve route was disabled, the port-forward service stopped,
and `books-cwa-dev` scaled to zero replicas. The UAT config and library PVCs
remain bound for rollback; `devspace purge` was intentionally not run because
it would delete those volumes. Production `books` remained 1/1 ready.

The next application task is a UI refresh, not a production data cutover.
To resume UAT deliberately, scale `books-cwa-dev` to one replica with the
explicit kubeconfig above and recreate a private review route; do not assume
the old Tailnet route is still active.

## Pastel UI review (2026-09-12)

UAT is resumed for the Pastel UI from source commit
`968dbc21f3aec991b769102c6a25b1fefdfaad5f` (application PR #7).
The GHCR-only build is GitHub Actions run `34720104372`; `uat.yaml` pins its
immutable image digest. Deploy with the DevSpace command above to reuse the
retained config and catalog PVCs.

The private review address is `https://shell-01.tailcff11.ts.net:18083/`.
Sign in with the existing UAT account and select **Pastel Theme**, or use
**Switch Theme** to cycle Standard → caliBlur → Pastel. Catalog-only limitations
from the prior review still apply.

The forwarding process runs as a transient user service on shell-01; it survives
the agent session and retries if the pod restarts. Recreate it after a host reboot:

```sh
systemd-run --user --unit=cwa-uat-portforward \
  --description='CWA dev review port forward' \
  --property=Restart=always --property=RestartSec=5 \
  /usr/local/bin/kubectl \
  --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig \
  -n books port-forward --address=127.0.0.1 svc/books-cwa-dev 18083:8083
sudo -n tailscale serve --bg --https=18083 http://127.0.0.1:18083
```

To pause the review while retaining the test data:

```sh
sudo -n tailscale serve --https=18083 off
systemctl --user stop cwa-uat-portforward.service
kubectl --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig \
  -n books scale deployment/books-cwa-dev --replicas=0
```

Verification: dev and production were both 1/1 ready; the private login URL
returned HTTP 200; served `pastel.css` matched the source SHA-256. The retained
UAT catalog contained 5,608 entries and SQLite `quick_check` returned `ok`.

## Pastel layout and palette follow-up (2026-09-12)

PR #9 updates the review to source
`4ca9fb24eacac196cae068a674928826a5e83289`, built by GHCR-only run
`34722711967`. The palette now uses sage navigation, cream pages, peach reading
panels, and lilac controls. `uat.yaml` records the immutable image.

Authenticated Chromium review covers home and full book details at 320, 390,
768, and 1440 pixels; real XHR popup loading, scrolling, and closing at phone
and desktop widths; mobile menu and focused search; profile, admin, advanced
search, regular search, and metadata edit navigation. Checks include viewport
bounds and description-before-metadata ordering. The focused suite has 35
passing tests; browser checks were rerun after the palette update.

The wider review reproduced a search freeze while cover thumbnails were being
scanned. Thread stacks identified a worker registering SQLite UDFs on the same
connection used by search. Cover scans now read a snapshot through a separate,
read-only SQLite connection. Repeat navigation/search checks confirm the app
stays responsive. Temporary diagnostic edits are discarded by image rollout.

The retained catalog still has no production book files or covers. Reader,
download, mail, provider integrations, and destructive admin actions are not
validated by this UI review. The legacy Docker Hub/ARM push workflow still has
its separate credentials/runner failures; this deployment uses the successful
GHCR-only workflow.

Final deployment verification: dev rolled out 1/1 ready with digest
`sha256:1dabdf02c74a0a60005f03445d2b90265a41c29b02ea165c8145ca62e144f67b`.
The container's stylesheet and thumbnail module hashes match source. The live
layout/popup and desktop/phone search sequence passed against this image;
login health checks remained HTTP 200. Production remained 1/1 ready.

## Rosé Pine Dawn palette refinement (2026-09-12)

PR #10 separates the navigation surfaces using tints of Rosé Pine Dawn's Rose
(`#d7827e`) and Iris (`#907aa9`) over Base (`#faf4ed`), with Dawn Surface
(`#fffaf3`) for controls. Source palette: https://rosepinetheme.com/palette/ingredients/.
The top bar uses Rose, the left menu uses Iris, and the sort strip uses warm
neutrals with a lilac selected state. Gentle gradients and low-opacity shadows
soften the boundaries. The peach/purple book detail treatment is retained.

Source commit: `cbdda6c505eb7beb4ec3512071b999aba0bfe829`.
GHCR-only build: `34723606171`. Eight responsive Chromium tests pass.
The deployed image is
`sha256:d265a14ee09cd7eb12fe0dd2c522f0ce8ada4812ce1b1b42b33cf4f967b9dd17`.
The deployed stylesheet hash matches the source. CI smoke/unit, browser security,
and Hyperion policy checks pass. The legacy Docker Hub/ARM workflow remains
separate from this successful GHCR-only build.
Final live checks passed for home/book pages at 390, 768, and 1440 pixels,
including distinct header/sidebar gradients, no horizontal overflow, and the
description above metadata. Real XHR details and login health returned HTTP 200.

## Header and interaction polish (2026-09-12)

PR #11 moves the library name into the top bar and reserves responsive space
for search/actions. The sidebar starts below the header. Directional gradients,
soft shadows, inset highlights, and short hover transitions add depth; reduced
motion disables movement. Source: `892f628dba9dda3ebbce641a7de9c24cf2b4daad`;
GHCR-only build: `34724331244`.

Eight browser regressions pass. Authenticated checks cover header alignment,
brand/search separation, and overflow at 320, 390, 768, 1024, 1280, and 1440px,
plus book description ordering and reduced-motion behavior.
Final deployed image:
`sha256:c3832db598ebe98000d560a2a3d840ac22fa0b423e8e6869d45fd603aa5b2a85`.
The stylesheet hash matches source. All six live viewport checks and the book/
reduced-motion checks passed against this image. CI smoke/unit, browser security,
and policy checks pass.

## Typography and brand mark (2026-09-12)

PR #12 unifies Pastel heading/control typography and pairs the existing bundled
Calibre-Web C mark with a compact wordmark. Other themes retain their branding;
custom instance names retain their text and accessible label. No new font or
image dependency is introduced. Source: `15447a9dedb3b4f1d853578e4e24ee9eba6a4eeb`;
GHCR-only build: `34725173014`. Thirty-one theme/browser regressions pass.

Deployed image: `sha256:894be5b11b140255e3c31cd825ab60b2b20896c7ffbfb4ca0b00a9d98bcd349c`.
Authenticated checks against the deployed image pass at 320, 390, 768, 1024,
1280, and 1440 pixels, including logo loading, header bounds, matching wordmark/
book-title font families, description ordering, and reduced motion. CI smoke/unit,
browser security, and Hyperion policy checks pass. The separate default Docker
build still fails its existing registry authentication; the GHCR UAT build passed.

## Discover shelf (2026-09-12)

PR #13 restores Standard's random-book shelf in Pastel by overriding caliBlur's
hidden section and fixed heading rules. The existing random selection, profile
visibility preference, and standalone Discover page behavior are preserved.
Source: `1db4752dd1abeb073d57d2159564a92d44bbf6f9`; GHCR UAT build: `34725992797`.
Image: `sha256:71f040bc680c91a5421b8c2b394a37af3b6f10b40441c4f5cb97edb120441042`.
The deployed stylesheet hash matches source. Thirty-one theme/browser tests pass;
CI smoke/unit, browser security, and Hyperion policy checks pass. The independent
default Docker registry build retains its existing authentication failure.
