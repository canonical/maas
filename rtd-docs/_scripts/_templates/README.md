# API Documentation Templates

This directory contains templates and content files used to generate the MAAS API v2 documentation.

## Files

### `api-v2-header.md`
Contains the introductory content that appears at the beginning of the API documentation, including:
- Overview of the RESTful MAAS API
- API versions information
- HTTP methods and parameter-passing guidelines

### `api-v2-footer.md`
Contains supplementary content that appears at the end of the API documentation, including:
- Power types and their parameters
- Pod types and their parameters

### `api-v2-template.md.j2`
Jinja2 template that defines the structure of the generated API documentation. The template receives:
- `header`: Content from `api-v2-header.md`
- `footer`: Content from `api-v2-footer.md`
- `version`: API version number from OpenAPI spec
- `license_name`: License name from OpenAPI spec
- `license_url`: License URL from OpenAPI spec
- `tags`: Dictionary of API endpoint groups, where each group contains a list of endpoints with formatted parameters, request bodies, and responses

## How to Modify

### Updating Introductory Text
Edit `api-v2-header.md` to change the header content that appears before the API Information section.

### Updating Power/Pod Types
Edit `api-v2-footer.md` to change the power types and pod types information.

### Changing Documentation Structure
Edit `api-v2-template.md.j2` to modify:
- How endpoints are organized and displayed
- The structure of dropdown sections
- Formatting of parameters, request bodies, and responses
- Any additional sections or styling

## Generating Documentation

Run the generation script from the `rtd-docs` directory:

```bash
python3 _scripts/generate_api_docs.py
```

This will:
1. Generate the OpenAPI specification from source code
2. Load the header, footer, and template files
3. Process the OpenAPI spec into the template data structure
4. Render the Jinja2 template
5. Write the output to `reference/api-reference/api-v2-generated.md`

## Note

These template files are automatically excluded from Sphinx documentation builds via the `exclude_patterns` configuration in `conf.py`. They are only used during the API documentation generation process.
