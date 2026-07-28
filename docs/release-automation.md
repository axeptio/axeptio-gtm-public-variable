# Release Automation

Releases are driven by [Conventional Commits](https://www.conventionalcommits.org/) and
[release-please](https://github.com/googleapis/release-please). Every merge to `master`
maintains a release PR; merging that PR cuts the release and publishes the new version to
the GTM Community Template Gallery history.

## Branch flow

```
feature branch ──PR──> master ──> release PR ──> tag + GitHub Release
                       (default)  (carries the metadata.yaml entry)
```

`master` is both the default branch and the release branch. There is no `develop` and no `main`.

Pull requests are merged with a **merge commit** (squash and rebase merges are disabled on this
repository), so every commit in the branch lands on `master` — and every one of them is parsed by
release-please to work out the next version. Merge commits themselves are ignored. Tidy the branch
history before merging; `Lint commits` will reject a non-conventional commit anywhere in it.

## Workflows

- **`.github/workflows/commitlint.yml`** (`Lint commits`) — runs on every PR with two jobs:

  | Job | What it checks |
  | --- | --- |
  | `Validate commit messages` | every commit in the PR, against `commitlint.config.mjs` — these are the ones release-please reads |
  | `Validate PR title` | the PR title is a valid Conventional Commit — hygiene today, and the safety net if squash-merging is ever enabled |

  This is what makes automated versioning possible: `fix:` → patch, `feat:` → minor,
  `feat!:` / `BREAKING CHANGE:` → major.

- **`.github/workflows/validate-gallery.yml`** (`Validate gallery contract`) — runs
  `scripts/validate-gallery.py` on every PR **and** on pushes to `master`. It guards the gallery
  submission contract: the Apache-2.0-only `LICENSE`, `categories` in `___INFO___`, every
  `versions[].sha` real and newest-first, the `# Latest version` marker, and the required files at
  the repo root. Breaking any of these silently delists the template 2–3 days later, with no
  feedback from Google.

- **`.github/workflows/release.yml`** (`Release`) — fires on push to `master`, in two jobs:

  | Job | What it does |
  | --- | --- |
  | `Maintain the release PR` | release-please scans commits since the last release, opens or updates a release PR that bumps `VERSION`, `CHANGELOG.md` and `.release-please-manifest.json`. Merging that PR tags the commit and publishes a GitHub Release. |
  | `Sign the release commit and sync metadata.yaml` | finds the open release PR by its `autorelease: pending` label, replays release-please's commit under the bot's GPG key, adds the `chore(metadata): sync version history for <tag>` commit, and force-pushes the branch. |

## GTM Gallery version history

The gallery publishes template versions from the `versions:` list in `metadata.yaml` — one entry
per published version, each a commit SHA plus change notes, in reverse chronological order.

`scripts/update-metadata-version.mjs` keeps that list in sync. It derives `changeNotes` from the
top section of `CHANGELOG.md` (already written by release-please on the release branch) and
prepends the entry directly under the `versions:` key. It uses only Node built-ins and edits the
file textually, so the licence header and existing entries are preserved byte for byte.

Two things differ from the sibling `axeptio-gtm-public-template`, both deliberate:

1. **The entry is committed to the release PR, not pushed to `master`.** `master` here is
   protected with a pull-request requirement, `enforce_admins`, required signed commits and no
   bypass allowance — nothing can push to it, including `axeptio-bot`. Adding the entry to the
   release branch means `VERSION`, `CHANGELOG.md`, `.release-please-manifest.json` and
   `metadata.yaml` all arrive in a single merge commit.
2. **The published SHA is the last commit that changed `template.tpl`**, not the release merge
   commit — which does not exist yet at that point. That is already this repository's convention:
   the original `Initial Version` entry points at the `Update template.tpl` commit. The gallery
   only requires a commit reachable from the default branch, and this one is the commit whose tree
   actually contains the released template.

A consequence worth knowing: if a release contains no change to `template.tpl` (a CI-only or
docs-only release), the resolved SHA is the one already at the top of `metadata.yaml`, the script
no-ops, and no gallery entry is added. That is correct — there is no new template to publish.

**Do not add `versions:` entries by hand.** The one thing still manual is publishing the new
version in the gallery UI once the entry has landed.

## Authentication

The workflow authenticates as **`axeptio-bot`**, not the default `GITHUB_TOKEN`. The
organisation forbids `GITHUB_TOKEN` from creating or approving pull requests
(`can_approve_pull_request_reviews: false`), so release-please cannot open its release PR without
a real bot account.

`master` also enforces **signed commits**, and GitHub refuses to merge a pull request containing an
unverified commit into such a branch (block code `invalid_signature`, *"Commits must have verified
signatures"*).

**release-please's own commit is unsigned.** It is created through the Git Data API, which does not
sign, so `chore(master): release X.Y.Z` lands as `verified: false, reason: unsigned`. On the
sibling `axeptio-gtm-public-template` this is survivable only because that repo has
`enforce_admins: false` — the org audit log shows a `protected_branch.policy_override` with
`overridden_codes: ["invalid_signature", …]` on *every* release merge there. This repo has
`enforce_admins: true` and no bypass allowance, so there is no override: an unsigned release commit
would make the release PR unmergeable, permanently.

The `Sign the release commit and sync metadata.yaml` job therefore **replays** release-please's
commit — same tree, same message, same author — under the bot's GPG key, appends the metadata
commit (also signed), and force-pushes the branch with `--force-with-lease`. Every commit in the
release PR then verifies, and the PR merges with no override.

Rewriting the branch is safe: release-please never reads the release branch's commits. It matches
the PR by `headBranchName` among open PRs carrying the `autorelease: pending` label, builds its
file changes from `master`, and builds the release itself from the merged PR's title, body and
merge commit. If it force-pushes a fresh unsigned commit on a later run, this job simply re-signs —
the flow is self-healing, and the "tip is already signed" guard makes a re-run a no-op.

| Secret | Used for | Source |
| --------------------- | -------------------------------------------- | --------- |
| `BOT_GITHUB_TOKEN` | release PR, release, pushing the release branch | Org-level |
| `BOT_GPG_PRIVATE_KEY` | signing every commit on the release branch | Org-level |

Both are org-level secrets shared with this repository — confirm with
`gh api repos/axeptio/axeptio-gtm-public-variable/actions/organization-secrets` (which needs no
`admin:org` scope, unlike listing the org's secrets directly).

## Why not the canonical Axeptio release automation?

Axeptio's canonical release automation (ENG-11756) is a pair of thin caller workflows —
`create-release-pr.yml` and `auto-release.yml` — that call reusable workflows hosted in
`axeptio/tech-scripts`.

**They cannot be used here.** This repository is **public** and `axeptio/tech-scripts` is
**internal**. GitHub only allows a public caller repository to use reusable workflows from
**public** repositories, so both callers fail at access time with `workflow was not found`
before running a single job. See
[Access to reusable workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/reusable-workflows).

`release-please-action` is a public action, so it has no such restriction. The sibling public
repositories `axeptio/axeptio-gtm-public-template` and `axeptio/axeptio-sgtm-public-template` use
the same approach, and this repo's setup is deliberately kept aligned with them.
