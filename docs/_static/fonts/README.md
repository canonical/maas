# Vendored Ubuntu Variable Fonts

This directory contains vendored copies of the Ubuntu variable fonts,
committed directly to the MAAS repository.

## Fonts

| File | Size | Variant | Unicode Range |
|------|------|---------|---------------|
| `Ubuntu-latin.woff2` | ~93 KB | Regular | Basic Latin |
| `Ubuntu-Italic-latin.woff2` | ~75 KB | Italic | Basic Latin |
| `UbuntuMono-latin.woff2` | ~31 KB | Monospace | Basic Latin |
| `Ubuntu-latin-extended.woff2` | ~110 KB | Regular | Latin Extended |
| `Ubuntu-cyrillic.woff2` | ~49 KB | Regular | Cyrillic |
| `Ubuntu-cyrillic-extended.woff2` | ~61 KB | Regular | Cyrillic Extended |
| `Ubuntu-greek.woff2` | ~31 KB | Regular | Greek |
| `Ubuntu-greek-extended.woff2` | ~31 KB | Regular | Greek Extended |

**Total size**: ~480 KB

## Source

- **Version**: `v0.896a` (Ubuntu / Ubuntu-Italic), `v0.869` (UbuntuMono)
- **Origin**: `https://assets.ubuntu.com/v1/`
- **URLs**: See `docs/_static/offline-fonts.css` for the mapping between local
  filenames and their upstream source URLs (also documented in the archived
  `fetch_offline_fonts.py` script if present in git history).

## Why Vendored?

These fonts are committed to the repository (rather than downloaded at build time)
for the following reasons:

1. **Offline builds**: MAAS documentation must build successfully in air-gapped/offline
   environments with no external network access.
2. **FIPS hardening**: Deployed MAAS documentation runs under a strict
   Content-Security-Policy (`font-src 'self'`) that prohibits loading fonts
   from external CDNs at runtime.
3. **Reproducibility**: Vendoring eliminates any risk of drift caused by CDN
   changes or upstream font updates between builds.
4. **Build reliability**: Removes dependency on assets.ubuntu.com availability
   at build time.

The upstream `canonical_sphinx` theme's `custom.css` declares `@font-face` rules
whose `src:` points to `https://assets.ubuntu.com/`. Our
`docs/_static/offline-fonts.css` re-declares the same rules with local URLs
pointing at the files in this directory, overriding the upstream references.

## Updating

To update the Ubuntu fonts:

1. Visit https://assets.ubuntu.com/ or inspect the latest
   `canonical_sphinx` theme's `custom.css` for updated font URLs
2. Download the new .woff2 files into this directory, preserving the filenames
3. Update `docs/_static/offline-fonts.css` if the `@font-face` descriptors change
4. Update the version numbers in this README
5. Rebuild the docs and verify no CSP violations in browser DevTools

## License

The Ubuntu font family is licensed under the [Ubuntu Font License 1.0](https://ubuntu.com/legal/font-licence).
