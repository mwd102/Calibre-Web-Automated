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
this instance.

The current private review route is
`https://shell-01.tailcff11.ts.net:18083/`. On shell-01, a persistent user
service forwards local port 18083 to `svc/books-cwa-dev:8083`, and Tailscale
Serve publishes that port to the Tailnet. The route has no Cloudflare or public
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
Do not use destructive library actions while reviewing this catalog. UAT's
`app.db`, users, and credentials remain separate. Removing the Job after
verification does not remove either catalog; `devspace purge` does remove the
UAT claim, so retain the backup first if needed.

`devspace purge` removes DevSpace-managed resources, including the UAT claims.
Export anything you want to retain before purging. Do not use it while UAT is
still in progress.

When UAT is complete, disable the Tailnet mapping with
`sudo tailscale serve --https=18083 off`, stop the forwarding service with
`systemctl --user stop cwa-uat-portforward.service`, and then run `devspace
purge` with the same explicit kubeconfig and namespace. These are separate
steps so the review route can be removed without deleting UAT data.
