# CSP Inline Script Hash Management

This directory contains `regiond.nginx.conf.template`, the nginx configuration
template that applies a strict Content-Security-Policy (CSP) header to hardened
MAAS deployments.

One inline script is whitelisted via SHA-256 hash. This document explains:

- Why the script is whitelisted
- The exact script body and its current hash
- How to regenerate the hash after upstream updates
- Why other inline scripts are intentionally not whitelisted

For the operator-facing CSP reference (header structure and directive rationale),
see `docs/reference/configuration-guides/security-hardening.md`.

## Background: CSP and FIPS/STIG Hardening

MAAS deployments running with hardening active (or on a FIPS host) emit a
strict Content-Security-Policy header from the region controller's nginx.
The `script-src` directive forbids inline scripts by default:

```
script-src 'self' 'sha256-...'
```

This aligns with FIPS and STIG security controls that restrict browser code
execution to same-origin, explicitly-authorised sources. Relaxing the policy
with `'unsafe-inline'` would defeat the control and is not acceptable in
hardened deployments.

However, the Furo documentation theme emits a small dark/light mode
initialisation script that must run before the page paints, or users see a
brief flash to the wrong theme on first load and the light/dark/auto toggle
fails to take effect on the first visit.

Rather than weakening the CSP, we whitelist this one specific script by its
SHA-256 hash. See [Security hardening](../../../../docs/explanation/security.md)
and the operator reference at
[`docs/reference/configuration-guides/security-hardening.md`](../../../../docs/reference/configuration-guides/security-hardening.md)
for the broader hardening/FIPS context.

## Whitelisted Script: Furo Dark/Light Mode Initialisation

### Current Hash

```
sha256-ySvT2PEZeueHGC1y2crNuNTfphBynFPP7i+U21fEgX0=
```

### Script Body

The Furo theme emits this exact inline `<script>` on every documentation page:

```html
<script>
  document.body.dataset.theme = localStorage.getItem("theme") || "auto";
</script>
```

**Important**: The hash covers the exact bytes between `<script>` and
`</script>`, **including all surrounding whitespace, indentation and
newlines**. A single-character change (even whitespace) invalidates the hash.

### Purpose

Reads the user's stored theme preference from `localStorage` and applies it to
the document's `<body>` element before the page renders. Without it:

1. The page briefly renders in the wrong theme (flash of unstyled content)
2. The light/dark/auto toggle does not take effect on the first visit
3. Subsequent visits still recover the preference, but the first paint is jarring

### Source

- **Theme**: [Furo](https://github.com/pradyunsg/furo)
- **Pinned version**: see `docs/requirements.txt` / `docs/requirements-dev.txt`

## Why Other Inline Scripts Are Not Whitelisted

The documentation build can emit other inline scripts. They are intentionally
left out of the CSP allowlist:

### canonical-sphinx `github_url` helper

Emits an inline script used by the feedback button. The feedback button rework
in MAAS no longer relies on this inline declaration, so it is not required
in hardened deployments.

### sphinx-reredirects MyST/RST redirect stubs

Emits inline `<script>` redirect stubs in generated HTML. Hardened MAAS
deployments are always offline / FIPS installs whose users navigate the docs
via the canonical URLs shipped with the snap and never hit the redirect stubs.

Keeping the `script-src` allowlist to a single hash minimises the CSP's
attack surface, which is the primary rationale for hardening in the first
place.

## Regenerating the Hash

The hash must be regenerated whenever the exact bytes of the whitelisted
inline script change. Common triggers:

- Furo is upgraded to a new version
- `docs/conf.py` is changed in a way that alters the emitted script
- A new inline script needs to be whitelisted

### When You Need to Regenerate

When a hardened MAAS deployment shows a CSP violation for the docs page, the
browser's developer console prints the expected hash directly. You can either
copy that hash or compute it locally with the procedure below.

### Step-by-Step Procedure

1. **Build the documentation** so the generated HTML reflects the current
   theme:

   ```bash
   make -C docs html
   ```

2. **Locate the script in the built HTML**:

   ```bash
   grep -rn "localStorage.getItem" docs/_build/html/ | head -1
   ```

3. **Extract the exact script body**. Open the HTML file and copy everything
   between `<script>` and `</script>`, including all leading/trailing
   whitespace and newlines. Paste it into the Python snippet below **between
   the triple-quoted string delimiters, preserving the whitespace exactly**.

4. **Compute the new hash**:

   ```bash
   python3 - <<'EOF'
   import hashlib, base64
   # Paste the exact script body between the <script> and </script> tags,
   # including any surrounding whitespace / newlines, into `script` below.
   script = """
     document.body.dataset.theme = localStorage.getItem("theme") || "auto";
   """
   h = hashlib.sha256(script.encode("utf-8")).digest()
   print("sha256-" + base64.b64encode(h).decode())
   EOF
   ```

5. **Update `regiond.nginx.conf.template`**: replace the old `sha256-...`
   value inside the `script-src` directive of the CSP header (inside the
   `{{if hardening}}` block) with the newly computed hash.

6. **Update this README**: replace the "Current Hash" value above with the
   new hash and note the new Furo version.

7. **Test**: rebuild the docs, deploy to a hardened MAAS (or serve locally
   with the strict CSP header) and confirm no CSP violations appear in the
   browser's developer console.

## Related Files

- `regiond.nginx.conf.template` — nginx config where the CSP header (and hash)
  is defined, inside the `{{if hardening}}` block
- `docs/reference/configuration-guides/security-hardening.md` — operator-facing
  CSP reference (directive structure and rationale)
- `docs/_static/fonts/README.md` — related vendored asset for `font-src 'self'`
- `src/maasserver/templates/swagger-ui-dist/README.md` — related vendored asset
  for `script-src 'self'` on the API pages
