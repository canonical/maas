# Vendored Swagger UI Distribution

This directory contains a vendored copy of [Swagger UI](https://github.com/swagger-api/swagger-ui)
distribution files, committed directly to the MAAS repository.

## Version

- **swagger-ui-dist**: `5.17.14`
- **Source**: https://unpkg.com/swagger-ui-dist@5.17.14/

## Files

| File | Size | Purpose |
|------|------|---------|
| `swagger-ui.css` | ~149 KB | Swagger UI stylesheet |
| `swagger-ui-bundle.js` | ~1.4 MB | Swagger UI JavaScript bundle (all presets included) |

## Why Vendored?

These files are committed to the repository (rather than downloaded at build time)
for the following reasons:

1. **Offline builds**: MAAS must build successfully in air-gapped/offline environments
   with no external network access.
2. **FIPS hardening**: Deployed MAAS instances run under a strict Content-Security-Policy
   (`script-src 'self'; font-src 'self'`) that prohibits loading assets from
   external CDNs at runtime.
3. **Reproducibility**: Vendoring eliminates any risk of version drift caused by
   CDN changes, deprecations, or supply-chain attacks between builds.
4. **Build reliability**: Removes dependency on unpkg.com availability at build time.

## Deployment

At snap build time (`snap/snapcraft.yaml`), these files are copied to
`$SNAP/usr/share/maas/web/static/swagger-ui-dist/` and served by nginx via the
`/MAAS/swagger-ui/` URL prefix (see `src/maasserver/templates/http/regiond.nginx.conf.template`).

They are consumed by both:
- V2 Swagger UI at `/MAAS/api/2.0/` (see `src/maasserver/templates/openapi.html`)
- V3 Swagger UI at `/MAAS/a/docs/` (see `src/maasapiserver/common/api/handlers/swagger.py`)

## Updating

To update to a newer Swagger UI version:

1. Choose a new pinned version from https://github.com/swagger-api/swagger-ui/releases
2. Download the new files:
   ```
   VERSION="X.Y.Z"
   cd src/maasserver/templates/swagger-ui-dist/
   wget -O swagger-ui.css "https://unpkg.com/swagger-ui-dist@${VERSION}/swagger-ui.css"
   wget -O swagger-ui-bundle.js "https://unpkg.com/swagger-ui-dist@${VERSION}/swagger-ui-bundle.js"
   ```
3. Update the version number in this README
4. Test both V2 (`/MAAS/api/2.0/`) and V3 (`/MAAS/a/docs/`) Swagger UI pages
5. Verify no CSP violations in browser DevTools

## License

Swagger UI is distributed under the Apache License 2.0.
See https://github.com/swagger-api/swagger-ui/blob/master/LICENSE for full text.
