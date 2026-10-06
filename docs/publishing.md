# Publishing and release gates

The user authorized new public `ops-` repositories under `Yash-PK`. Existing
repositories must not be overwritten or silently reused. `.portfolio.json`
records this scope. No cloud or container-package publication is authorized.

After reviewing every outgoing file, license, documentation claim and diff:

```bash
make gate
git status --short
git diff --cached --stat
python3 scripts/publish.py --owner Yash-PK
python3 scripts/publish.py --owner Yash-PK --execute
```

The script is credential-free. It checks clean status, reruns gates, verifies
the authenticated personal account, requires a definitive repository-not-found
response and uses the current `gh repo create --help` interface. It refuses an
existing remote or collision and never force-pushes or changes visibility.
It verifies owner, visibility, branch and remote SHA after creation.

If authentication is blocked, run `gh auth login --hostname github.com` locally;
never paste credentials in chat. The underlying manual creation command, after
the same gates, from this repository is:

```bash
gh repo create Yash-PK/ops-linux-operations-toolkit --public --source . --remote origin --push
```

Inspect the Actions run for that exact SHA. Pending or failed CI is not a release
success. Versioned releases require local gates, Linux integration, completed
clean-clone validation and passing CI. No release is necessary for a work-in-
progress repository. Proposed branch protection after checks exist: require
the `validate` job on pull requests, disallow force-push/deletion and retain a
documented maintainer recovery path. Changing repository rules remains a
separately reviewed operation.
