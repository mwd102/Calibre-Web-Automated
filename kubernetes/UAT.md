# Hyperion UAT copy

`devspace.yaml` deploys `books-cwa-dev` into the existing `books` namespace.
It has separate config and library claims, a disposable ingest directory, and
its own GHCR pull-secret projection. It does not mount the production Books
claim or publish a public route. DevSpace owns the resources labelled
`hyperion.mwd.lol/owner: manual`; Argo CD continues to own `books`.

Use the explicit shell-01 Hyperion kubeconfig and namespace:

```sh
devspace deploy --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig -n books
kubectl --kubeconfig /home/homelab/Repos/Hyperion/.state/kubeconfig -n books rollout status deployment/books-cwa-dev
```

For a local browser session, run `devspace dev` with the same flags. It forwards
port 8083. The fresh application's initial administrator login is documented in
the repository README; change that password on first login before inviting
other reviewers. No SMTP credentials or production book data are copied into
this instance.

The initial review should cover login, selecting Standard and caliBlur themes,
search and book details in each theme, upload/ingest of a disposable book,
metadata editing, shelves, and the admin settings. Test Kobo, OAuth, LDAP,
mail delivery, and external metadata providers only after configuring separate
UAT credentials or fixtures for those paths.

`devspace purge` removes DevSpace-managed resources, including the UAT claims.
Export anything you want to retain before purging. Do not use it while UAT is
still in progress.
