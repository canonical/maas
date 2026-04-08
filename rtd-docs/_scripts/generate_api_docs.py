#!/usr/bin/env python3
#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate API documentation in Markdown format from OpenAPI specification.

This script generates API documentation by generating the OpenAPI spec from source
and converting it to Markdown suitable for inclusion in the RTD documentation.

Usage:
    python3 rtd-docs/_scripts/generate_api_docs.py
"""

from pathlib import Path
import sys
from typing import Any

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


def get_openapi_spec() -> dict[str, Any]:
    """Generate the OpenAPI specification from source.

    Returns:
        OpenAPI specification dictionary.

    Raises:
        RuntimeError: If generation fails.
    """
    print("Generating OpenAPI spec from source...")
    scripts_dir = Path(__file__).parent
    sys.path.insert(0, str(scripts_dir))

    try:
        from get_api_spec import get_openapi_spec as generate_spec

        spec = generate_spec()
        print("✓ Successfully generated OpenAPI spec from source")
        return spec
    except Exception as e:
        raise RuntimeError(
            f"Failed to generate OpenAPI spec from source: {e}"
        ) from e


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
        for _, (path, method, operation, path_item) in enumerate(endpoints):
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


def generate_docs() -> None:
    """Generate API documentation from OpenAPI specification.

    Raises:
        RuntimeError: If OpenAPI spec generation fails.
    """
    spec = get_openapi_spec()

    output_dir = (
        Path(__file__).resolve().parent.parent / "reference" / "api-reference"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / "api-v2-generated.md"
    markdown = generate_markdown(spec)
    output_file.write_text(markdown)


def main():
    """Main entry point for CLI usage."""
    generate_docs()


if __name__ == "__main__":
    main()
