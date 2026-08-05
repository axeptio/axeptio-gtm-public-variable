# Axeptio Consent State — Google Tag Manager Variable

This repository hosts the **Axeptio Consent State** variable template for the
[GTM Community Template Gallery](https://tagmanager.google.com/gallery).

The variable returns one Axeptio consent signal, so tags can be conditioned on it without any
custom JavaScript:

| Signal | What it returns |
| --- | --- |
| `axeptio_authorized_vendors` | the vendors the visitor has consented to, as an array |
| `consent_mode` | the Google Consent Mode v2 state (`ad_storage`, `analytics_storage`, `ad_user_data`, `ad_personalization`) |
| `gpp_string`, `mspa_mode`, `gpc_active`, `consent_type` | the GPP fields, on GPP-enabled projects |

It reads the data layer first and falls back to the Axeptio consent cookies, so on a repeat
visit it still resolves for tags that fire before the widget has pushed its events. Two signals
have no cookie to fall back to — `gpc_active` and `consent_type` are derived from the project
configuration the widget fetches and are never stored — and a consent cookie compressed by the
widget's `compressUserCookie` setting cannot be decoded inside Tag Manager's sandbox, so
`consent_mode` and `mspa_mode` then resolve from the data layer only.

The variable only *reports* consent state; it cannot apply it. Setting Google Consent Mode is
the job of the [Axeptio CMP tag template](https://github.com/axeptio/axeptio-gtm-public-template),
which is also what writes this consent state to the data layer in the first place.

For setup instructions and usage in GTM, see:

👉 **[Axeptio Help Center — Conditioning a GTM tag on the Axeptio consent state](https://support.axeptio.eu/en/articles/348776-conditioning-a-gtm-tag-to-fire-only-when-a-specific-event-occurs)**

For any questions, contact [support@axeptio.eu](mailto:support@axeptio.eu).

## Contributing

See [CONTRIBUTING.md](./CONTRIBUTING.md) for the commit message conventions and the
licensing terms contributions are accepted under.

Releases are automated from [Conventional Commits](https://www.conventionalcommits.org/);
`VERSION`, `CHANGELOG.md` and the `versions:` history in `metadata.yaml` are all generated.
See [docs/release-automation.md](./docs/release-automation.md).

## License

Licensed under the [Apache License 2.0](./LICENSE).

The [Community Template Gallery](https://developers.google.com/tag-platform/tag-manager/templates/gallery)
requires the `LICENSE` file to contain **only** Apache 2.0 — a template whose licence
does not match is removed from the gallery automatically. Do not replace it.
