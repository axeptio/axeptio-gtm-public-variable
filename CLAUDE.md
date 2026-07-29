# Project Instructions for AI Agents

This file provides instructions and context for AI coding agents working on this project.

## Architecture Overview

This repo is **not an application** — it is the public source for the **Axeptio Consent State**
variable in the [GTM Community Template Gallery](https://tagmanager.google.com/gallery). Two files
are the product:

- **`template.tpl`** — the GTM custom template, of type `MACRO` (a *variable*, not a tag), in
  Google's own block format: `___INFO___`, `___TEMPLATE_PARAMETERS___`,
  `___SANDBOXED_JS_FOR_WEB_TEMPLATE___`, `___WEB_PERMISSIONS___` and `___TESTS___`. Its
  `___TERMS_OF_SERVICE___` header is Google's mandatory gallery boilerplate — **never edit it**.
  The variable reads the `axeptio_authorized_vendors` key from the data layer and returns it.
- **`metadata.yaml`** — the gallery's published version history (`versions:`, one commit SHA +
  `changeNotes` per version, newest first). This is what the gallery actually serves.

Everything else is licensing (`LICENSE`, `CONTRIBUTING.md`) or release automation
(`.github/workflows/`, `scripts/`, `release-please-config.json`, `VERSION`).

The sibling repo `axeptio/axeptio-gtm-public-template` is the *tag* counterpart and uses the same
tooling. Keep the two aligned, but note one deliberate divergence, documented in
[docs/release-automation.md](docs/release-automation.md): here the `metadata.yaml` sync is
committed to the release PR, because `master` in this repo accepts no direct pushes at all.

## Build & Test

There is **no build, no compile, and no test runner** — nothing to install beyond PyYAML.
Validation is by inspection plus these checks:

```bash
python3 scripts/validate-gallery.py    # THE important one — see below (needs 3.7+, PyYAML)
python3 -c "import json; json.load(open('release-please-config.json'))"
python3 -c "import json; json.load(open('.release-please-manifest.json'))"
node --check scripts/update-metadata-version.mjs
```

`validate-gallery.py` enforces the **Community Template Gallery contract** — the LICENSE being
Apache-2.0-only, `categories` in `___INFO___`, every `versions[].sha` real and newest-first, the
`# Latest version` marker, and the required files at the repo root. Breaking any of these silently
delists the template 2–3 days later with no feedback from Google, which is exactly how SUP-1008
happened on the sibling repo. CI runs it on every PR **and** on pushes to `master`; run it locally
before touching `LICENSE`, `metadata.yaml` or `template.tpl`.

It also checks `template.tpl` for **internal consistency**, which is not a gallery rule but has
nowhere else to be caught: every block present and parsing (JSON for `___INFO___`,
`___TEMPLATE_PARAMETERS___`, `___WEB_PERMISSIONS___`; YAML for `___TESTS___`), `read_data_layer`
pinned to `allowedKeys: specific`, the `signal` selector and the `read_data_layer` `keyPatterns`
offering exactly the same keys, and `node --check` over the sandboxed JS and every test scenario.
The selector/permission parity check is the load-bearing one — an option with no matching key
pattern returns `undefined` at runtime with no error anywhere.

**CI cannot run the `___TESTS___` scenarios.** The Test API (`runCode`, `mock`, `assertThat`) only
exists inside Tag Manager's proprietary sandboxed-JS interpreter; there is no CLI, no API endpoint,
and no third-party runner. To exercise the template, import `template.tpl` into a GTM container and
use the **Tests** tab, then confirm real behaviour in **Preview** against a page running the widget.

## Conventions & Patterns

- **Conventional Commits are mandatory.** PRs land as **merge commits** (squash and rebase are
  disabled), so *every* commit in the branch reaches `master` and is what release-please parses —
  tidy the history before merging. CI (`Lint commits`) checks every commit and the PR title.
  Types/scopes live in `commitlint.config.mjs`.
- **Single branch: `master`.** It is both the default and the release branch. No `develop`, no
  `main`.
- **Never hand-edit `VERSION`, `CHANGELOG.md`, `.release-please-manifest.json`, or the
  `versions:` list in `metadata.yaml`** — all four are generated. See
  [docs/release-automation.md](docs/release-automation.md).
- **`master` accepts no direct pushes**, by anyone, including `axeptio-bot`: it requires a pull
  request, enforces the rules on admins, requires signed commits, and has no bypass allowance. Any
  automation that needs to change a tracked file must do it through a pull request, and **every
  commit it produces must be GPG-signed** — an unverified commit anywhere in a PR makes that PR
  unmergeable, with no override available. This is why the release workflow re-signs
  release-please's own (unsigned) commit rather than merely adding to it.
- **Licensing is load-bearing — do not change `LICENSE`.** The Community Template Gallery
  requires it to contain **only** Apache 2.0, and removes a template whose licence does not
  match. Replacing it with Axeptio's proprietary terms is what caused SUP-1008: the sibling
  template was delisted within ~24h. Gallery distribution and proprietary licensing are mutually
  exclusive — if the licence must change, the template has to leave the gallery, and that is
  a business decision, not a code change.
- **Before touching `LICENSE`, `metadata.yaml`, `template.tpl` or the default branch**, check
  them against the
  [gallery requirements](https://developers.google.com/tag-platform/tag-manager/templates/gallery).
  All three files must be at the repo root on the default branch. Deleting or malforming
  `LICENSE` or `metadata.yaml` triggers automatic removal, and re-listing needs a manual
  resubmission — it is not automatic.
- **Do not deploy the `axeptio/tech-scripts` release automation here.** It is the org standard for
  private repos only; this repo is public and the reusable workflows are unreachable from it.
- `gh` is the canonical interface for GitHub work.
