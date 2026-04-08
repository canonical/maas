#!/usr/bin/env python3
#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate API documentation in Markdown format from OpenAPI specification.

This script generates API documentation by reading the OpenAPI YAML file
and converting it to Markdown suitable for inclusion in the RTD documentation.

Usage:
    # Auto-detect (try to load or generate from source)
    python3 rtd-docs/_scripts/generate_api_docs.py

    # Read from file
    python3 rtd-docs/_scripts/generate_api_docs.py openapi.yaml

    # Read from stdin
    bin/maas-region generate_oapi_spec | python3 rtd-docs/_scripts/generate_api_docs.py -
"""

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Any

import yaml

# Response status code descriptions
HTTP_STATUS_CODES = {
    200: "OK",
    201: "CREATED",
    202: "ACCEPTED",
    204: "NO CONTENT",
    400: "BAD REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT FOUND",
    409: "CONFLICT",
    500: "INTERNAL SERVER ERROR",
    503: "SERVICE UNAVAILABLE",
}


def find_maas_root() -> Path:
    """Find the MAAS root directory."""
    # Start from script location and go up to find MAAS root
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "src" / "maasserver").is_dir():
            return current
        current = current.parent
    raise FileNotFoundError("Could not find MAAS root directory")


def get_openapi_spec(spec_file: str | None = None) -> dict[str, Any] | None:
    """Load or generate the OpenAPI specification.

    Args:
        spec_file: Path to OpenAPI YAML file, or None to auto-detect.
                   Use '-' to read from stdin.

    Returns:
        OpenAPI specification dictionary or None if unavailable.

    Tries in order:
    1. Read from stdin if spec_file is '-'
    2. Load from spec_file if provided
    3. Generate from source using get_api_spec module
    4. Load existing openapi.yaml from MAAS root
    5. Generate it using bin/maas-region
    6. Return None if all fail
    """
    # Read from stdin
    if spec_file == "-":
        print("Reading OpenAPI spec from stdin...")
        try:
            return yaml.safe_load(sys.stdin)
        except Exception as e:
            print(
                f"Warning: Failed to parse YAML from stdin: {e}",
                file=sys.stderr,
            )
            return None

    # Load from provided file
    if spec_file:
        spec_path = Path(spec_file)
        if spec_path.exists():
            print(f"Loading OpenAPI spec from {spec_path}")
            with open(spec_path) as f:
                return yaml.safe_load(f)
        else:
            print(
                f"Warning: Spec file not found: {spec_path}", file=sys.stderr
            )
            return None

    # Try to find MAAS root for auto-detection
    try:
        maas_root = find_maas_root()
    except FileNotFoundError:
        print("Warning: Could not find MAAS root directory", file=sys.stderr)
        return None

    # Try to generate from source directly (preferred method)
    try:
        print("Generating OpenAPI spec from source...")
        scripts_dir = Path(__file__).parent
        sys.path.insert(0, str(scripts_dir))
        from get_api_spec import get_openapi_spec as generate_spec
        
        spec_yaml = generate_spec()
        print("✓ Successfully generated OpenAPI spec from source")
        return yaml.safe_load(spec_yaml)
    except Exception as e:
        print(
            f"Warning: Failed to generate spec from source: {e}",
            file=sys.stderr,
        )
        # Fall through to other methods

    openapi_file = maas_root / "openapi.yaml"

    # Try to load existing file
    if openapi_file.exists():
        print(f"Loading existing OpenAPI spec from {openapi_file}")
        with open(openapi_file) as f:
            return yaml.safe_load(f)

    # Try to generate it using bin/maas-region
    maas_region_bin = maas_root / "bin" / "maas-region"
    if maas_region_bin.exists():
        print(f"Generating OpenAPI spec using {maas_region_bin}...")
        try:
            result = subprocess.run(
                [str(maas_region_bin), "generate_oapi_spec"],
                capture_output=True,
                text=True,
                check=True,
                cwd=maas_root,
            )
            return yaml.safe_load(result.stdout)
        except subprocess.CalledProcessError as e:
            print(
                f"Warning: Failed to generate OpenAPI spec: {e}",
                file=sys.stderr,
            )
            if e.stderr:
                print(f"Error output: {e.stderr}", file=sys.stderr)
        except Exception as e:
            print(
                f"Warning: Unexpected error generating spec: {e}",
                file=sys.stderr,
            )

    return None


def format_parameter(
    param: dict[str, Any], endpoint_params: list[dict[str, Any]] = None
) -> str:
    """Format a parameter for markdown output."""
    name = param["name"]
    param_type = param.get("schema", {}).get("type", "string")
    required = "Required" if param.get("required", False) else "Optional"
    description = param.get("description", "")
    param_in = param.get("in", "query")

    # Check if it's a path parameter
    is_path_param = param_in == "path" or (
        endpoint_params
        and any(
            p["name"] == name and p["in"] == "path" for p in endpoint_params
        )
    )

    if is_path_param:
        return f"- **`{{{name}}}`** (*{param_type}*, path parameter, {required}): {description}"
    else:
        return f"- **`{name}`** (*{param_type}*, {required}): {description}"


def format_request_body(request_body: dict[str, Any]) -> list[str]:
    """Format request body schema for markdown output."""
    lines = []

    if "multipart/form-data" in request_body["content"]:
        schema = request_body["content"]["multipart/form-data"]["schema"]
        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])

        for prop_name, prop_info in properties.items():
            prop_type = prop_info.get("type", "string")
            is_required = (
                "Required" if prop_name in required_fields else "Optional"
            )
            description = prop_info.get("description", "")
            lines.append(
                f"  - **`{prop_name}`** (*{prop_type}*, {is_required}): {description}"
            )

    return lines


def format_response(status_code: str, response: dict[str, Any]) -> list[str]:
    """Format a response for markdown output."""
    status_name = HTTP_STATUS_CODES.get(int(status_code), "")
    description = response.get("description", "")

    lines = [f"  **HTTP {status_code} {status_name}**"]
    if description:
        lines.append(f"  ")
        lines.append(f"  {description}")

    if "content" in response:
        content_types = list(response["content"].keys())
        if content_types:
            content_type = content_types[0]
            lines.append(f"  ")
            lines.append(f"  Content type: `{content_type}`")

    return lines


def generate_markdown(spec: dict[str, Any]) -> str:
    """Convert OpenAPI specification to Markdown documentation."""
    lines = []

    # Header
    lines.append("# MAAS API v2 Reference")
    lines.append("")
    lines.append(spec["info"]["description"])
    lines.append("")

    # API information
    lines.append("## API Information")
    lines.append("")
    lines.append(f"**Version:** {spec['info']['version']}")
    lines.append("")
    lines.append(
        f"**License:** [{spec['info']['license']['name']}]({spec['info']['license']['url']})"
    )
    lines.append("")

    # Group paths by tag
    paths_by_tag: dict[str, list[tuple[str, str, dict, dict]]] = {}

    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if method == "parameters" or not isinstance(operation, dict):
                continue

            tags = operation.get("tags", ["Uncategorized"])
            tag = tags[0] if tags else "Uncategorized"

            if tag not in paths_by_tag:
                paths_by_tag[tag] = []

            paths_by_tag[tag].append(
                (path, method.upper(), operation, path_item)
            )

    # Generate documentation for each tag
    for tag in sorted(paths_by_tag.keys()):
        lines.append(f"## {tag}")
        lines.append("")
        lines.append(f"Operations for {tag.lower()} resources.")
        lines.append("")

        endpoints = sorted(paths_by_tag[tag])
        for idx, (path, method, operation, path_item) in enumerate(endpoints):
            operation_id = operation.get("operationId", "")
            summary = operation.get("summary", "")
            description = operation.get("description", "")
            deprecated = operation.get("deprecated", False)

            # Create dropdown title
            endpoint_display = f"{method} /MAAS/api/2.0{path}"
            if summary:
                dropdown_title = f"{endpoint_display}: {summary}"
            else:
                dropdown_title = endpoint_display

            # Mark deprecated in title
            if deprecated:
                dropdown_title = f"~~{dropdown_title}~~"

            # Start collapsible dropdown
            lines.append(f"````{{dropdown}} {dropdown_title}")
            lines.append("")

            # Description
            if description:
                lines.append(f"  {description}")
                lines.append("")

            if deprecated:
                lines.append("  ```{warning}")
                lines.append("  This endpoint is deprecated.")
                lines.append("  ```")
                lines.append("")

            lines.append(f"  **Operation ID:** `{operation_id}`")
            lines.append("")

            # Parameters
            endpoint_params = path_item.get("parameters", [])
            operation_params = operation.get("parameters", [])
            all_params = endpoint_params + operation_params

            if all_params:
                lines.append("  **Parameters:**")
                lines.append("")
                for param in all_params:
                    # Indent parameter lines
                    param_line = format_parameter(param, endpoint_params)
                    lines.append(f"  {param_line}")
                lines.append("")

            # Request body
            if "requestBody" in operation:
                lines.append("  **Request body (multipart/form-data):**")
                lines.append("")
                body_lines = format_request_body(operation["requestBody"])
                lines.extend(body_lines)
                lines.append("")

            # Responses
            if "responses" in operation:
                lines.append("  **Responses:**")
                lines.append("")
                for status_code, response in sorted(
                    operation["responses"].items()
                ):
                    response_lines = format_response(status_code, response)
                    lines.extend(response_lines)
                    lines.append("")

            # Close dropdown
            lines.append("````")
            lines.append("")

    return "\n".join(lines)


def generate_placeholder(reason: str) -> str:
    """Generate a placeholder message when spec cannot be loaded."""
    return f"""# MAAS API v2 Reference

```{{warning}}
The API documentation could not be automatically generated.
{reason}
```

## Generating the API Documentation

To generate the API documentation, first build the OpenAPI specification from the MAAS root directory:

```bash
# From the MAAS root directory
make openapi.yaml
```

Then rebuild the documentation:

```bash
# From rtd-docs directory
make clean
make serve
```

## Alternative: View the API Documentation

You can view the API documentation through:

- **Web UI**: Access your MAAS instance at `/MAAS/api/docs/`
- **OpenAPI Spec**: Download from `/MAAS/api/2.0/openapi.yaml`
- **Online Docs**: Visit [maas.io/docs](https://maas.io/docs)

## API Overview

The MAAS API provides programmatic access to all MAAS functionality. Every feature available in the UI is also accessible through the API.

For authentication and basic usage, see:
- [How to login to the MAAS API](api-login.md)
- [Managing your API profile](api-profile.md)
"""


def generate_docs(spec_file: str | None = None) -> None:
    """Generate API documentation from OpenAPI specification.
    
    Args:
        spec_file: Path to OpenAPI YAML file, '-' for stdin, or None to auto-detect.
    """
    # Load or generate OpenAPI spec
    print("Loading OpenAPI specification...")
    spec = get_openapi_spec(spec_file)

    # Write to output file
    output_dir = (
        Path(__file__).resolve().parent.parent / "reference" / "api-reference"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "api-v2-generated.md"

    if spec is None:
        # Generate placeholder
        print("⚠ Could not load OpenAPI spec, generating placeholder...")
        markdown = generate_placeholder(
            "The openapi.yaml file could not be found or generated."
        )
    else:
        # Convert to Markdown
        print("Converting to Markdown...")
        markdown = generate_markdown(spec)

    print(f"Writing to {output_file}...")
    output_file.write_text(markdown)

    print("✓ API documentation generated successfully!")


def main():
    """Main entry point for CLI usage."""
    parser = argparse.ArgumentParser(
        description="Generate API documentation from OpenAPI specification"
    )
    parser.add_argument(
        "spec_file",
        nargs="?",
        default=None,
        help="Path to OpenAPI YAML file, or '-' to read from stdin. "
        "If not provided, auto-detects or generates the spec.",
    )
    args = parser.parse_args()

    generate_docs(args.spec_file)


if __name__ == "__main__":
    main()
