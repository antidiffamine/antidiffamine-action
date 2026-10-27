# AntiDiffamine

See the clean diff between two branches of a force-push to a pull request.

When a PR branch is rebased onto a newer base and force-pushed, GitHub's "compare" view between the before and after commits mixes the author's edits with every commit that landed on the base branch in the meantime. AntiDiffamine rebases the old commits onto the new base first, then diffs. You get only the changes made inside the PR, alongside a `git range-diff` and any merge conflicts the rebase hit.

Results always appear in the Actions run summary. On top of that, you can switch each of these features on or off:

| Feature | Input | Default | Needs |
|---|---|---|---|
| PR comment linking to the diff | `comment` | on | `pull-requests: write` |
| `diff.html` uploaded as a workflow artifact | `html_enabled` | on | — |
| `diff.html` hosted on GitHub Pages | `pages` | off | `contents: write`, `html_enabled`, [Pages setup](#hosted-html-pages-optional) |

## Usage

```yaml
# .github/workflows/antidiffamine.yml
name: AntiDiffamine

on:
  pull_request_target:
    types: [synchronize]

permissions:
  contents: read        # write if pages: true
  pull-requests: write  # for the PR comment

jobs:
  antidiffamine:
    runs-on: ubuntu-latest
    steps:
      - uses: antidiffamine/antidiffamine-action@v1
        with:
          comment: true
          pages: false
```

No secrets are needed; the default `GITHUB_TOKEN` is used. Grant only the permissions for the features you turn on.

`pull_request_target` is used so the token can comment on PRs from forks. The action only clones the PR commits and runs `git rebase` / `git diff` on them; it never executes code from the PR.

If your organization restricts the default token, also enable **Settings → Actions → General → Workflow permissions → Read and write permissions**.

## Inputs

| Input | Default | Description |
|---|---|---|
| `source` | `github.event.before` | Commit SHA before the force-push. |
| `target` | `github.event.after` | Commit SHA after the force-push. |
| `base_branch` | `github.base_ref` | Base branch the PR targets. |
| `repo` | `github.repository` | `owner/repo` containing the commits. |
| `token` | `github.token` | Token used to clone, push to `gh-pages` and comment. |
| `html_enabled` | `true` | Render `diff.html` and upload it as a workflow artifact. |
| `pages` | `false` | Publish `diff.html` to GitHub Pages under `gh-pages/runs/<run-id>/`. Requires `html_enabled`. |
| `comment` | `true` | Post a PR comment with links to the diff (PR events only). |
| `fail_on_rebase_failure` | `true` | Fail the step when the rebase cannot be completed even with `-X theirs`, so only a partial diff is shown. |

Outside of `pull_request` events (e.g. `workflow_dispatch`), pass `source`, `target` and `base_branch` explicitly.

## Outputs

| Output | Description |
|---|---|
| `bases_match` | `true` when source and target share the same merge base. No rebase is needed, so the diff and comment are skipped. |
| `had_conflicts` | `true` when the first rebase hit merge conflicts. |
| `rebase_failed` | `true` when the second rebase (`-X theirs`) also failed. |
| `page_url` | URL of the hosted diff page; empty if `pages` is off or Pages is not set up. |

## How it works

1. Compute the fork point of `source` and of `target` on `base_branch`.
2. If they are equal, a plain compare is already accurate, so the action stops there.
3. Otherwise rebase `source_base..source` onto `target_base`. If that conflicts, record the conflict markers and retry with `-X theirs`.
4. Diff the rebased result against `target`, and run `git range-diff source_base..source target_base..rebased`.
5. Write everything to the job summary and, if `pages: true`, to `gh-pages/runs/<run-id>/index.html`.

## Hosted HTML pages (optional)

Off by default. To turn it on:

1. Set `pages: true` and change the workflow permission to `contents: write`.
2. Create an empty `gh-pages` branch:
   ```bash
   git switch --orphan gh-pages && git commit --allow-empty -m "init gh-pages" && git push origin gh-pages
   ```
3. **Settings → Pages → Build and deployment**: Source **Deploy from a branch**, branch `gh-pages`, folder `/ (root)`.

If `pages: true` but Pages isn't enabled in the repo settings, the deploy step is skipped and only the Actions summary link is posted.

Each run adds `runs/<run-id>/` to `gh-pages`. To keep the branch from growing forever, copy [`examples/cleanup-pages.yml`](examples/cleanup-pages.yml) to `.github/workflows/`. It runs daily and deletes pages older than 3 days.

## Minimal setup

Summary only: no comment, no artifact, no Pages, read-only token:

```yaml
permissions:
  contents: read

jobs:
  antidiffamine:
    runs-on: ubuntu-latest
    steps:
      - uses: antidiffamine/antidiffamine-action@v1
        with:
          comment: false
          html_enabled: false
```

## Running on a specific pair of commits

```yaml
on:
  workflow_dispatch:
    inputs:
      source: { required: true }
      target: { required: true }
      base_branch: { required: true, default: main }

jobs:
  antidiffamine:
    runs-on: ubuntu-latest
    permissions:
      contents: read
    steps:
      - uses: antidiffamine/antidiffamine-action@v1
        with:
          source: ${{ inputs.source }}
          target: ${{ inputs.target }}
          base_branch: ${{ inputs.base_branch }}
```

## License

[MIT](LICENSE)
