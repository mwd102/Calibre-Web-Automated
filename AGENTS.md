<!-- hyperion-context:start -->
## Hyperion deployment context

This project targets the Hyperion K3s environment. Before changing deployment,
networking, storage, ingress, authentication, observability, or secret handling,
search the globally configured Hyperion OKF memory with `okf_search`. Inspect only
relevant results with `okf_show`, and check path-scoped governance when editing
Hyperion deployment declarations.

Hyperion memory is a retrieval layer, not live-state proof. Hyperion's reachable
Git desired state, controller state, and verified cluster state remain authoritative;
treat disagreement as drift to investigate. Never copy credentials or resolved
secret values into this repository or into OKF memory.

Agents own the task Git lifecycle after this one-time bootstrap. Before changing
files, inspect the canonical checkout and registered worktrees, fetch current
`origin/main`, and create a unique task branch in an isolated worktree at
`/home/homelab/Worktrees/<repo>/<task>`. Never edit the canonical checkout, reuse
another task's worktree, create durable worktrees under `/tmp`, force-push, or
delete `main`. Review and validate the exact diff, publish through a pull request,
and remove only the worktree created for the current task after its work is safely
published or intentionally abandoned. These narrowly scoped lifecycle operations
are required for Hyperion-targeted work; preserve stricter repository rules for
all other Git operations.
<!-- hyperion-context:end -->
