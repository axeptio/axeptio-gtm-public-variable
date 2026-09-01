<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/logo-axeptio-white.svg">
    <img src="assets/logo-axeptio.svg" alt="Axeptio" width="180">
  </picture>
</p>

# Axeptio Consent State — Google Tag Manager Variable

[![GTM Gallery](https://img.shields.io/badge/GTM_Gallery-Axeptio_Consent_State-4285F4?logo=googletagmanager&logoColor=white)](https://tagmanager.google.com/gallery/#/owners/axeptio/templates/axeptio-gtm-public-variable)
[![Release](https://img.shields.io/github/v/release/axeptio/axeptio-gtm-public-variable)](https://github.com/axeptio/axeptio-gtm-public-variable/releases)
[![License](https://img.shields.io/github/license/axeptio/axeptio-gtm-public-variable)](./LICENSE)
[![Validate gallery contract](https://github.com/axeptio/axeptio-gtm-public-variable/actions/workflows/validate-gallery.yml/badge.svg)](https://github.com/axeptio/axeptio-gtm-public-variable/actions/workflows/validate-gallery.yml)
[![Test template](https://github.com/axeptio/axeptio-gtm-public-variable/actions/workflows/test.yml/badge.svg)](https://github.com/axeptio/axeptio-gtm-public-variable/actions/workflows/test.yml)

The official [Axeptio](https://www.axept.io/) consent-state variable for Google Tag Manager
(web containers).

It returns one Axeptio consent signal — the vendors the visitor authorized, the Google Consent
Mode v2 state, or a GPP field — so your other tags can be conditioned on consent without any
custom JavaScript.

**[▶ Axeptio Consent State in the Community Template Gallery](https://tagmanager.google.com/gallery/#/owners/axeptio/templates/axeptio-gtm-public-variable)**

## Installing

In your GTM **web** container: **Templates → Variable Templates → Search Gallery**, look for
**Axeptio Consent State**, and add it to your workspace. Then create a variable from the template
and pick the signal you want.

The variable only *reports* consent state — it cannot apply it. Loading the CMP and setting
Google Consent Mode is the job of the
[Axeptio CMP tag](https://github.com/axeptio/axeptio-gtm-public-template), which is also what
publishes this consent state in the first place.

Step-by-step setup lives in the Help Center:

👉 **[Axeptio Help Center — Conditioning a GTM tag on the Axeptio consent state](https://support.axeptio.eu/en/articles/348776-conditioning-a-gtm-tag-to-fire-only-when-a-specific-event-occurs)**

## Configuration

| Field | Default | What it does |
| --- | --- | --- |
| **Consent signal** | Authorized vendors | Which signal the variable returns. See [below](#the-signals). |
| **Authorized vendor to test** | *(empty)* | Name one vendor to get a boolean instead of the list. See [below](#testing-a-single-vendor). |
| **Read from** | Data layer, falling back to the cookies | Where the signal is read from. See [below](#read-from). |
| **Cookie names** | *(the Axeptio defaults)* | Only needed if the site renames the consent cookies. |

### The signals

| Signal | Returns | Published with |
| --- | --- | --- |
| **Authorized vendors** | array of vendor names, e.g. `["google_analytics", "facebook_pixel"]` — or a boolean, if you [name a vendor](#testing-a-single-vendor) | `axeptio_update` |
| **Google Consent Mode state** | object: `ad_storage`, `analytics_storage`, `ad_user_data`, `ad_personalization` (each `granted`/`denied`), plus `version` | `axeptio_update`, on projects with Consent Mode enabled |
| **GPP string** | the raw GPP string | `gpp_consent_given` / `gpp_consent_refused` / `gpp_consent_updated` |
| **MSPA mode** | `opt-out` or `service-provider` | as above |
| **GPC active** | boolean | as above |
| **GPP consent type** | `opt-in` or `opt-out` | as above |

The GPP signals only appear on GPP-enabled projects.

### Testing a single vendor

A trigger cannot be gated on an array. Fill in **Authorized vendor to test** with one Axeptio
vendor identifier and the variable returns a boolean instead — no second variable, no lookup
table:

| Consent state | Vendor field empty | Vendor field = `google_analytics` |
| --- | --- | --- |
| `["google_analytics", "facebook_pixel"]` | the array | `true` |
| `["facebook_pixel"]` | the array | `false` |
| `[]` | the array | `false` |
| nothing readable yet | `undefined` | `false` |

The name is matched **exactly and case-sensitively** against the vendor identifier —
`google_analytics`, not `Google Analytics`.

That last row is the one to know about. Every other signal here returns `undefined` while the
consent state is unreadable — first visit, widget not loaded, no cookie yet. This one returns
`false`, because it answers "is this vendor authorized" and "not known yet" is not a yes. It is
fail-closed by design: a tag gated on it will not fire before consent is readable. If you need to
tell "refused" apart from "not yet known", leave the field empty and test the array.

The field applies to **Authorized vendors** only, and is hidden for the other signals.

### Read from

The data layer only carries a signal once the Axeptio widget has pushed it. On a repeat visit
that can be later than the tags you want to gate — the consent cookies, by contrast, are already
present when the page starts parsing.

| Mode | Behaviour |
| --- | --- |
| **Data layer, falling back to the cookies** *(default)* | reads the data layer, and only reads a cookie when that key has not been pushed yet |
| **Data layer only** | the pre-1.1.0 behaviour; use it if you want strictly event-driven semantics |
| **Axeptio cookies only** | never reads the data layer |

Two limits apply to the cookie fallback, both by nature rather than by omission:

- **GPC active** and **GPP consent type** are computed by the widget from the project
  configuration it fetches, and are never stored in a cookie. They resolve from the data layer
  only.
- A consent cookie compressed by the widget's `compressUserCookie` setting cannot be decoded
  inside Tag Manager's sandbox. **Google Consent Mode state** and **MSPA mode** then fall back to
  nothing rather than to a wrong value.

The fallback triggers only when the data layer value is strictly *undefined*, never when it is
merely falsy — `GPC active: false` and an empty GPP string are real answers, and are returned
as-is.

<details>
<summary><strong>Cookie names (advanced)</strong></summary>

Only change these if the site overrides the matching setting in `window.axeptioSettings`.

| Field | Default | SDK setting |
| --- | --- | --- |
| Consent JSON cookie | `axeptio_cookies` | `jsonCookieName` |
| Authorized vendors cookie | `axeptio_authorized_vendors` | `authorizedVendorsCookieName` |
| GPP string cookie | `axeptio_gpp_string` | `gppCookieName` |

A renamed cookie must **also** be added to this template's cookie permission in your container,
under **Templates → the template → Permissions → Reads cookie value**. Without that, reading it
is blocked and the variable silently returns nothing.

</details>

## Upgrading from 1.0.x

1.1.0 added the signal selector and the cookie fallback. Variables saved before it deserialise
with no signal and no source, and keep working — they resolve to **Authorized vendors**, read
from the data layer with the cookie fallback.

That last part is a behaviour change worth knowing about: on a repeat visit the variable now
resolves *earlier* than it used to. A tag gated on "this variable is undefined" will fire sooner
than before. Switch **Read from** to *Data layer only* to restore the old timing exactly.

## Related templates

| Template | Purpose |
| --- | --- |
| [axeptio-gtm-public-template](https://github.com/axeptio/axeptio-gtm-public-template) | The **Axeptio CMP tag** — loads the CMP and drives Google Consent Mode v2 |
| [axeptio-sgtm-public-template](https://github.com/axeptio/axeptio-sgtm-public-template) | **Server-side** GTM tag |

## Support

- **A bug in this template** — open an [issue](https://github.com/axeptio/axeptio-gtm-public-variable/issues).
- **Your Axeptio account, configuration or billing** — [support@axeptio.eu](mailto:support@axeptio.eu).

## Versioning

Releases follow [Semantic Versioning](https://semver.org/); see
[CHANGELOG.md](./CHANGELOG.md) and the
[releases](https://github.com/axeptio/axeptio-gtm-public-variable/releases).

The Community Template Gallery refreshes on Google's own schedule, so a new version usually
appears there **two to three days** after it is released here.

### Testing a version before the gallery has it

Every release carries the template as an attachment — `axeptio-consent-state-vX.Y.Z.tpl` on the
[releases page](https://github.com/axeptio/axeptio-gtm-public-variable/releases). Download it and
import it into a container with **Templates → New → ⋮ → Import**, and you get that exact version
without waiting for Google.

Use the attachment rather than the copy of `template.tpl` on a branch. The file in the repository
moves as work lands, so it names no version; the attachment is fixed to its release, which is what
makes "tested on v1.2.0" mean something.

An imported template is local to your container and is not linked to the gallery copy. When the
gallery catches up, delete the imported one and add the gallery version instead, or the two will
sit side by side.

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the commit message conventions, how to run the
template's tests, the gallery contract this repository has to satisfy, and the licensing terms
contributions are accepted under.

`VERSION`, `CHANGELOG.md` and the `versions:` history in `metadata.yaml` are all generated —
see [docs/release-automation.md](./docs/release-automation.md).

## License

Licensed under the [Apache License 2.0](./LICENSE).

The [Community Template Gallery](https://developers.google.com/tag-platform/tag-manager/templates/gallery)
requires the `LICENSE` file to contain **only** Apache 2.0 — a template whose licence
does not match is removed from the gallery automatically. Do not replace it.
