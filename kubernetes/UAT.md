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
