# Axeptio Consent State — Google Tag Manager Variable

This repository hosts the **Axeptio Consent State** variable template for the
[GTM Community Template Gallery](https://tagmanager.google.com/gallery).

The variable reads the `axeptio_authorized_vendors` key from the data layer and returns the
list of vendors the visitor has consented to, so tags can be conditioned on it without any
custom JavaScript.

It is the companion to the [Axeptio CMP tag template](https://github.com/axeptio/axeptio-gtm-public-template),
which is what writes that consent state to the data layer in the first place.

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
