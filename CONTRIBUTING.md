# How to Contribute

We'd love to accept your patches and contributions to this project. There are
just a few small guidelines you need to follow.

## Contributions and licensing

This template is distributed under the [Apache License 2.0](./LICENSE). By
submitting a contribution you agree that it is provided under, and may be
redistributed as part of this project under, that licence.

The [Community Template Gallery](https://developers.google.com/tag-platform/tag-manager/templates/gallery)
requires the `LICENSE` file to contain **only** Apache 2.0. A template whose
licence does not match is removed from the gallery automatically, so the licence
cannot be changed while the template is distributed there.

## Code reviews

All submissions, including submissions by project members, require review. We
use GitHub pull requests for this purpose. Consult
[GitHub Help](https://help.github.com/articles/about-pull-requests/) for more
information on using pull requests.

## Testing a template change

The `___TESTS___` block in `template.tpl` holds YAML test scenarios. They run in two places from
that one definition — in the GTM UI **Tests** tab, and headlessly in CI:

```bash
npm ci
npm test
```

The runner executes the **real** `___SANDBOXED_JS_FOR_WEB_TEMPLATE___` source, so a change that
breaks the variable breaks a test. If you change template behaviour, add a scenario for it rather
than a separate test file.

Scenario **names** may only contain letters, numbers, spaces, hyphens and underscores. GTM's editor
silently refuses to save a template whose test name contains punctuation such as `.` or `/`, so the
runner fails the build on one instead of letting you discover it in the UI.

Write scenarios that can actually fail. A scenario asserting only that a result is `undefined` often
passes for the wrong reason — several distinct paths through this template return `undefined`. Where
the distinction matters, assert on *how* the answer was reached (`assertApi(...).wasNotCalled()`),
not just on the value.

## The gallery contract

This variable template is published through the
[Community Template Gallery](https://developers.google.com/tag-platform/tag-manager/templates/gallery),
which imposes requirements on the repository itself — not just on the template code. Break one and
Google **silently delists the template** a couple of days later, with no notification on the pull
request and no submission-status page to check.

A CI check, `Validate gallery contract`, runs on every pull request and on pushes to `master`. Run
it yourself before touching `LICENSE`, `metadata.yaml` or `template.tpl`:

```bash
pip install pyyaml          # one-time; the script needs Python 3.7+
python3 scripts/validate-gallery.py
```

It reports every violation at once. The rules most easily broken by accident:

- **`LICENSE` must contain *only* Apache 2.0.** Not "Apache 2.0 plus a notice" — only. Changing it
  removes the template from the gallery; that is what happened to the sibling Axeptio tag template
  in SUP-1008.
- **`___INFO___` must declare `categories`** — 1 to 3 values from Google's list, most relevant first.
- **`versions:` entries must be real commits on `master`, newest first**, with the `# Latest version`
  marker on the top entry. Never edit this list by hand; it is generated on release.

## Commit & pull request conventions

This project uses [Conventional Commits](https://www.conventionalcommits.org/)
to drive automated [Semantic Versioning](https://semver.org/) and changelog
generation via [release-please](https://github.com/googleapis/release-please).

A commit / PR title must follow:

```
<type>(<optional scope>): <description>
```

**Allowed types**

| Type       | Effect on version | Reaches the gallery? | Use for                                 |
| ---------- | ----------------- | -------------------- | --------------------------------------- |
| `feat`     | minor bump        | yes                  | a new feature                           |
| `fix`      | patch bump        | yes                  | a bug fix                               |
| `perf`     | patch bump        | yes                  | performance improvement                 |
| `revert`   | patch bump        | yes                  | reverting a previous commit             |
| `docs`     | none              | no                   | documentation only                      |
| `refactor` | none              | no                   | code change that isn't a fix or feature |
| `build`    | none              | no                   | build system or dependencies            |
| `test`     | none              | no                   | tests                                   |
| `ci`       | none              | no                   | CI / GitHub Actions changes             |
| `chore`    | none              | no                   | maintenance / tooling                   |

**Pick the type by who is affected, not by how big the change feels.** A release
publishes a new version to the Community Template Gallery, so `feat`/`fix`/`perf`/`revert`
should be reserved for changes a GTM user installing the variable would notice. Anything
that cannot change the variable's behaviour — a README, a CI job, a refactor — belongs in
the lower group.

Typing a CI or tooling change as `fix` is the easy mistake, because "fix" describes
almost any repair. `fix(ci):` still has type `fix`, so it bumps the version and its
subject is published on the public listing.

A breaking change is signalled by a `!` after the type (e.g. `feat!: ...`) or a
`BREAKING CHANGE:` footer, and triggers a major bump.

**Suggested scopes:** `template`, `metadata`, `docs`, `ci`.

Examples:

```
feat(template): expose the vendor list as a nested object
fix(template): return an empty list when the data layer key is absent
docs: clarify the import steps
```

**Important notes**

- Pull requests are merged with a **merge commit** (squash and rebase are
  disabled), so **every individual commit** lands on `master` and is parsed by
  release-please. The `Lint commits` CI check lints them all — a stray
  `wip: fixup` in your branch will fail the check, so tidy the history before
  requesting review.
- **The PR title can cut a release on its own.** The repository is set to
  `merge_commit_message: PR_TITLE`, so GitHub writes the title into the *body* of
  the merge commit, and release-please reads it as a changelog entry like any
  other commit:

  ```
  subject: Merge pull request #14 from axeptio/docs/readme-reference
  body:    docs: add a logo header, badges and a field-level reference to the README
  ```

  A PR contributes its commits **plus** its title. A PR titled `fix:` therefore
  bumps the version and publishes that line to the public gallery listing even if
  every commit inside it is `chore`/`ci`/`docs`. `Validate PR title` is the only
  guard on that string — it is not merely hygiene.
- Releases, `CHANGELOG.md`, `VERSION`, git tags, GitHub Releases, and the
  `versions:` history in `metadata.yaml` are **all generated automatically**. Do
  not edit versions or the changelog by hand. See
  [docs/release-automation.md](./docs/release-automation.md).

## Community Guidelines

Please be respectful and constructive in issues and pull requests. For questions
about the template or Axeptio, see the [Axeptio documentation](https://www.axept.io/)
or contact [support@axeptio.eu](mailto:support@axeptio.eu).
