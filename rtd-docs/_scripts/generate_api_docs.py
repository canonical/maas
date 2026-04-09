#!/usr/bin/env python3
#  Copyright 2026 Canonical Ltd.  This software is licensed under the
#  GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate API documentation in Markdown format from OpenAPI specification.

This script generates API documentation by generating the OpenAPI spec from source
and converting it to Markdown suitable for inclusion in the RTD documentation.

Usage:
    python3 rtd-docs/_scripts/generate_api_docs.py
"""

from collections import defaultdict
from pathlib import Path
import sys
from typing import Any

from jinja2 import Environment, FileSystemLoader

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
                f"- **`{prop_name}`** (*{prop_type}*, {is_required}): {description}"
            )

    return lines


def format_response(status_code: str, response: dict[str, Any]) -> str:
    """Format a response for markdown output."""
    status_name = HTTP_STATUS_CODES.get(int(status_code), "")
    description = response.get("description", "")

    lines = [f"**HTTP {status_code} {status_name}**"]
    if description:
        lines.append("")
        lines.append(f"{description}")

    if "content" in response:
        content_types = list(response["content"].keys())
        if content_types:
            content_type = content_types[0]
            lines.append("")
            lines.append(f"Content type: `{content_type}`")

    return "\n".join(lines)


def prepare_template_data(spec: dict[str, Any]) -> dict[str, Any]:
    """Prepare data structure for Jinja2 template rendering.

    Args:
        spec: OpenAPI specification dictionary.

    Returns:
        Dictionary containing all data needed for template rendering.
    """
    # Group paths by tag
    paths_by_tag: dict[str, list[dict[str, Any]]] = defaultdict(list)

    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if method == "parameters" or not isinstance(operation, dict):
                continue

            tags = operation.get("tags", ["Uncategorized"])
            tag = tags[0] if tags else "Uncategorized"

            # Prepare endpoint data
            endpoint_params = path_item.get("parameters", [])
            operation_params = operation.get("parameters", [])
            all_params = endpoint_params + operation_params

            # Format parameters
            formatted_params = []
            for param in all_params:
                formatted_params.append(format_parameter(param, endpoint_params))

            # Format request body
            formatted_request_body = []
            if "requestBody" in operation:
                formatted_request_body = format_request_body(operation["requestBody"])

            # Format responses
            formatted_responses = []
            if "responses" in operation:
                for status_code, response in sorted(operation["responses"].items()):
                    formatted_responses.append(format_response(status_code, response))

            endpoint_data = {
                "path": path,
                "method": method.upper(),
                "operation_id": operation.get("operationId", ""),
                "summary": operation.get("summary", ""),
                "description": operation.get("description", ""),
                "deprecated": operation.get("deprecated", False),
                "parameters": formatted_params,
                "request_body": formatted_request_body,
                "responses": formatted_responses,
            }

            paths_by_tag[tag].append(endpoint_data)

    # Sort endpoints within each tag
    for tag in paths_by_tag:
        paths_by_tag[tag] = sorted(
            paths_by_tag[tag], key=lambda x: (x["path"], x["method"])
        )

    return {
        "version": spec["info"]["version"],
        "license_name": spec["info"]["license"]["name"],
        "license_url": spec["info"]["license"]["url"],
        "tags": dict(sorted(paths_by_tag.items())),
    }


def generate_markdown(spec: dict[str, Any]) -> str:
    """Convert OpenAPI specification to Markdown documentation using Jinja2.

    Args:
        spec: OpenAPI specification dictionary.

    Returns:
        Rendered markdown documentation.
    """
    scripts_dir = Path(__file__).parent
    templates_dir = scripts_dir / "_templates"

    # Load header and footer content
    header_file = templates_dir / "api-v2-header.md"
    footer_file = templates_dir / "api-v2-footer.md"

    header_content = header_file.read_text()
    footer_content = footer_file.read_text()

    # Prepare template data
    template_data = prepare_template_data(spec)
    template_data["header"] = header_content
    template_data["footer"] = footer_content

    # Setup Jinja2 environment
    env = Environment(
        loader=FileSystemLoader(templates_dir),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    # Render template
    template = env.get_template("api-v2-template.md.j2")
    return template.render(**template_data)


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
    print(f"✓ Successfully generated API documentation at {output_file}")


def main():
    """Main entry point for CLI usage."""
    generate_docs()


if __name__ == "__main__":
    main()
