#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Discover MAAS CLI commands by constructing argparse tree from source."""

import argparse
import json
import os
import re
import sys

try:
    import importlib.metadata as _ilm
except ImportError:
    _ilm = None


re_usage_line = re.compile(r"^usage\s*:?", re.IGNORECASE)
re_opt_desc = re.compile(r"^(?P<opt>\S.*?\S)\s{2,}(?P<desc>.+)$")

builtins = {
    "login",
    "logout",
    "list",
    "refresh",
    "init",
    "config",
    "status",
    "migrate",
    "apikey",
    "configauth",
    "config-tls",
    "config-vault",
    "createadmin",
    "changepassword",
    "msm",
}


def add_repo_src_to_path():
    """Add repository src directory to Python path."""
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    src_dir = os.path.join(repo_root, "src")
    if os.path.isdir(src_dir) and src_dir not in sys.path:
        sys.path.insert(0, src_dir)


def build_parser(argv0="maas"):
    """Build and return the MAAS CLI argument parser."""
    if _ilm is not None:
        _orig_distribution = getattr(_ilm, "distribution", None)

        def _fake_distribution(name):
            if name == "maas":

                class _Dummy:
                    version = "0.0.0"

                return _Dummy()
            if _orig_distribution is None:
                raise ModuleNotFoundError(
                    f"distribution not available for {name}"
                )
            return _orig_distribution(name)

        if _orig_distribution is not None:
            _ilm.distribution = _fake_distribution

    try:
        from maascli.parser import prepare_parser

        snap_env_was_set = "SNAP" in os.environ
        if not snap_env_was_set:
            try:
                import maascli.snap
                os.environ["SNAP"] = "/snap/maas/current"
                os.environ["SNAP_DATA"] = "/var/snap/maas/current"
                os.environ["SNAP_COMMON"] = "/var/snap/maas/common"
            except ImportError:
                pass

        fake_argv = [argv0]
        parser = prepare_parser(fake_argv)

        if not snap_env_was_set and "SNAP" in os.environ:
            del os.environ["SNAP"]
            if "SNAP_DATA" in os.environ:
                del os.environ["SNAP_DATA"]
            if "SNAP_COMMON" in os.environ:
                del os.environ["SNAP_COMMON"]

        return parser
    except ImportError:
        raise


def generate_api_description_from_source():
    """Generate API description from source code without needing a live server."""
    try:
        if "DJANGO_SETTINGS_MODULE" not in os.environ:
            os.environ.setdefault(
                "DJANGO_SETTINGS_MODULE", "maasserver.djangosettings.settings"
            )

        try:
            import django
            django.setup()
        except ImportError:
            return None

        try:
            from maasserver.api.doc import get_api_description
            return get_api_description()
        except ImportError:
            return None
    except Exception:
        return None


def try_register_api_profile(parser):
    """Register API profile from source-generated API description."""
    try:
        from maascli.api import register_resources, profile_help

        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                if any(name not in builtins for name in action.choices.keys()):
                    return True

        description = generate_api_description_from_source()
        if description is None:
            return False

        from maascli.utils import api_url as _normalize_api_url

        base_url = os.environ.get(
            "MAAS_INTROSPECT_URL", "http://localhost:5240/MAAS/"
        )
        api_base = _normalize_api_url(base_url)

        profile = {
            "name": "local",
            "url": api_base,
            "credentials": ("key", "secret", "token"),
            "description": description,
        }
        sub = parser.subparsers.add_parser(
            profile["name"],
            help="Interact with %(url)s" % profile,
            description=(
                "Issue commands to the MAAS region controller at "
                "%(url)s." % profile
            ),
            epilog=profile_help,
        )
        register_resources(profile, sub)
        return True
    except Exception:
        return False


def get_subparsers(parser):
    """Extract all subparsers from the argument parser."""
    subparsers = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparsers.append(action)
    return subparsers


def collect_optional_rows(parser):
    """Collect optional argument rows from parser."""
    rows = []
    for action in parser._get_optional_actions():
        if not getattr(action, "option_strings", None):
            continue
        help_text = getattr(action, "help", None)
        if help_text == argparse.SUPPRESS or help_text == "==SUPPRESS==":
            continue
        option_sig = ", ".join(action.option_strings)
        metavar = None
        if getattr(action, "metavar", None):
            metavar = action.metavar
        elif getattr(action, "nargs", None) not in (0, None) and getattr(
            action, "type", None
        ) is not bool:
            metavar = action.dest.upper().replace("-", "_")
        if metavar:
            option_sig = f"{option_sig} {metavar}"
        help_text = help_text or ""
        help_text = str(help_text).replace("|", r"\|")
        help_text = "<br>".join(line.strip() for line in help_text.splitlines()).strip()
        rows.append(
            {
                "option": option_sig,
                "effect": help_text,
                "flags": list(action.option_strings),
                "required": bool(getattr(action, "required", False)),
                "choices": (
                    list(getattr(action, "choices", []) or [])
                    if getattr(action, "choices", None) is not None
                    else None
                ),
                "nargs": getattr(action, "nargs", None),
                "metavar": getattr(action, "metavar", None) or metavar,
                "dest": getattr(action, "dest", None),
                "default": (
                    None
                    if getattr(action, "default", None) is argparse.SUPPRESS
                    else getattr(action, "default", None)
                ),
            }
        )
    return rows


def node_key(path):
    """Generate a key from a command path."""
    return " ".join(path)


def parse_simple_sections(help_text, description):
    """Parse additional sections from help text (e.g., 'Examples:', 'See also:')."""
    additional_sections = []
    lines = help_text.splitlines()
    current_section = None
    current_section_content = []

    for line in lines:
        s = line.strip()
        if (
            s.endswith(":")
            and not s.startswith("-")
            and s not in ["usage:", "options:", "optional arguments:"]
        ):
            if current_section is not None and current_section_content:
                additional_sections.append(
                    {
                        "title": current_section,
                        "content": "\n".join(current_section_content),
                    }
                )
            current_section = s.rstrip(":")
            current_section_content = []
        elif current_section is not None:
            current_section_content.append(line)
        elif (
            s
            and not s.startswith(("usage", "options", "optional arguments"))
            and s != description.strip()
        ):
            current_section_content.append(line)

    if current_section is not None and current_section_content:
        additional_sections.append(
            {
                "title": current_section,
                "content": "\n".join(current_section_content),
            }
        )

    return additional_sections


def describe_parser(parser, path):
    """Describe a parser node with its usage, options, and metadata."""
    usage = parser.format_usage().strip()
    description = parser.description or ""
    epilog = parser.epilog or ""

    accepts_json = ":param" in (epilog or "")
    returns_json = False

    additional_sections = []
    if len(path) == 2 and path[0] == "maas":
        try:
            help_text = parser.format_help()
            additional_sections = parse_simple_sections(help_text, description)
        except Exception:
            pass

    return {
        "key": node_key(path),
        "argv": path[1:],
        "usage": usage,
        "options": collect_optional_rows(parser),
        "children": [],
        "overview": description.strip()
        or (
            "CLI help for: "
            + re.sub(r"^\s*usage\s*:?\s*", "", usage)
        ),
        "example": "",
        "keywords_text": str(epilog).strip(),
        "accepts_json": accepts_json,
        "returns_json": returns_json,
        "additional_sections": additional_sections,
    }


def walk(parser, path):
    """Recursively walk the parser tree and build a node structure."""
    node = describe_parser(parser, path)
    subparsers = get_subparsers(parser)
    for sp in subparsers:
        for name, subparser in sorted(sp.choices.items()):
            child_path = path + [name]
            child_node = walk(subparser, child_path)
            node["children"].append(child_node)
    return node


def flatten(node):
    """Flatten a tree of nodes into a list."""
    out = [
        {k: v for k, v in node.items() if k != "children"}
    ]
    for c in node.get("children", []):
        out.extend(flatten(c))
    return out


def normalize_drill_down(content):
    """Normalize drill-down section content by pairing commands with descriptions."""
    entries = []
    i = 0
    while i < len(content):
        line_text = content[i].strip()
        if not line_text or line_text == "COMMAND":
            i += 1
            continue
        if "  " in line_text:
            entries.append(line_text)
            i += 1
            continue
        desc = ""
        if i + 1 < len(content):
            next_line = content[i + 1]
            if next_line.startswith(" ") or next_line.startswith("\t"):
                desc = next_line.strip()
                i += 2
            else:
                i += 1
        else:
            i += 1
        if desc:
            entries.append(f"{line_text}  {desc}")
        else:
            entries.append(line_text)
    return "\n".join(entries)


def _parse_positional_args_compact(full_text, matches):
    """Parse positional args when multiple args are on one line (compact format)."""
    entries = []
    for i, match in enumerate(matches):
        arg_name = match.group(1)
        desc_start = match.end()
        desc_end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        desc = full_text[desc_start:desc_end].strip()
        if desc.endswith(".") and i + 1 < len(matches):
            desc = desc[:-1].strip()
        if desc:
            entries.append(f"{arg_name}  {desc}")
        else:
            entries.append(arg_name)
    return entries


def _parse_positional_args_multiline(content):
    """Parse positional args when each arg is on separate lines (multiline format)."""
    entries = []
    i = 0
    while i < len(content):
        head = content[i]
        head_stripped = head.strip()
        name = head_stripped
        first_desc = ""
        m = re.match(r"^(?P<name>\S.*?)\s{2,}(?P<desc>.+)$", head_stripped)
        if m:
            name = m.group("name").strip()
            first_desc = m.group("desc").strip()
        if not name:
            i += 1
            continue
        desc_parts = []
        if first_desc:
            desc_parts.append(first_desc)
        j = i + 1
        while j < len(content):
            next_line = content[j]
            if next_line.startswith(" ") or next_line.startswith("\t"):
                desc_parts.append(next_line.strip())
                j += 1
            else:
                break
        desc = " ".join(desc_parts).strip()
        if desc:
            entries.append(f"{name}  {desc}")
        else:
            entries.append(name)
        i = j
    return entries


def normalize_positional_args(content):
    """Normalize positional arguments section by extracting argument names and descriptions."""
    full_text = " ".join(line.strip() for line in content if line.strip())
    matches = list(re.finditer(r'(\S+)\s{2,}', full_text))

    if len(matches) > 1:
        entries = _parse_positional_args_compact(full_text, matches)
    else:
        entries = _parse_positional_args_multiline(content)
    
    return "\n".join(entries)


def extract_usage_and_overview(lines, command):
    """Extract usage string and overview description from help text lines."""
    def is_usage_line(s):
        return re_usage_line.match(s) is not None

    usage_lines = []
    in_usage = False
    for line in lines:
        s = line.strip()
        if is_usage_line(s):
            in_usage = True
            usage_lines.append(s)
            continue
        elif in_usage and s and not s.startswith(
            ("options:", "optional arguments:")
        ):
            usage_lines.append(s)
        elif in_usage and (
            s.startswith("options:") or s.startswith("optional arguments:")
        ):
            break
        elif in_usage and not s:
            continue
        elif in_usage:
            break

    usage = " ".join(usage_lines) if usage_lines else f"usage: maas {command} [-h]"

    in_usage_section = False
    overview = ""
    for line in lines:
        s = line.strip()
        if is_usage_line(s):
            in_usage_section = True
            continue
        if in_usage_section and s and not s.startswith(
            ("usage", "options", "optional arguments", "[")
        ):
            overview = s
            break

    if not overview:
        overview = f"CLI help for: maas {command} [-h]"

    return usage, overview


def finalize_option(current_option, current_desc_lines):
    """Create option dict from option text and description lines."""
    desc = " ".join(current_desc_lines).strip()
    opt_text = current_option
    if not desc:
        m = re_opt_desc.match(opt_text) or re.match(
            r"^(?P<opt>\S.*?\S)\s{2,}(?P<desc>.+)$", opt_text
        )
        if m:
            opt_text = m.group("opt").strip()
            desc = m.group("desc").strip()
    return {"option": opt_text, "effect": desc}


def finalize_section(
    current_section,
    current_section_content,
    current_section_content_raw,
    section_raw_lines,
):
    """Finalize a section by normalizing content and tracking raw lines."""
    content = "\n".join(current_section_content)
    title_lower = current_section.strip().lower()
    if title_lower == "drill down":
        content = normalize_drill_down(current_section_content)
    elif title_lower == "positional arguments":
        content = normalize_positional_args(current_section_content)

    section_raw_lines.update(rl.strip() for rl in current_section_content_raw)
    return {"title": current_section, "content": content}


def collect_additional_text(lines, overview, section_raw_lines):
    """Collect text that doesn't belong to any specific section."""
    additional_text = []
    for line in lines:
        s = line.strip()
        if (
            s
            and not s.startswith(("usage", "options", "optional arguments"))
            and not s.endswith(":")
            and s not in section_raw_lines
            and s != overview
            and not s.startswith(("-", "--"))
        ):
            additional_text.append(line)

    if additional_text:
        extra = " ".join(l.strip() for l in additional_text if l.strip())
        return extra.replace("|", r"\|")
    return ""


def handle_section_header(state, line_stripped, section_raw_lines, options, additional_sections):
    """Handle transition to a new section header. Returns updated parsing state dict."""
    if state["current_section"] is not None:
        if state["current_section"] in ("options", "optional arguments"):
            if state["current_option"] is not None:
                options.append(finalize_option(
                    state["current_option"], state["current_desc_lines"]
                ))
        elif state["current_section_content"]:
            additional_sections.append(
                finalize_section(
                    state["current_section"],
                    state["current_section_content"],
                    state["current_section_content_raw"],
                    section_raw_lines,
                )
            )

    section_raw_lines.update(rl.strip() for rl in state["current_section_content_raw"])
    new_section = line_stripped.rstrip(":")
    in_options = new_section in ("options", "optional arguments")

    return {
        "current_section": new_section,
        "current_option": None,
        "current_desc_lines": [],
        "current_section_content": [],
        "current_section_content_raw": [],
        "in_options": in_options,
        "in_other_section": not in_options,
    }


def process_option_line(line, s, current_option, current_desc_lines, options):
    """Process a single line in the options section. Returns updated option state."""
    if not s:
        return current_option, current_desc_lines

    if s.startswith("-"):
        if current_option is not None:
            options.append(finalize_option(current_option, current_desc_lines))
        if m := re_opt_desc.match(s):
            return m.group("opt").strip(), [m.group("desc").strip()]
        return s, []
    elif current_option is not None and (line.startswith(" ") or line.startswith("\t")):
        current_desc_lines.append(s)

    return current_option, current_desc_lines


def parse_help_sections(lines, overview):
    """Parse options and additional sections from argparse help text."""
    options = []
    additional_sections = []
    section_raw_lines = set()
    
    state = {
        "current_section": None,
        "current_section_content": [],
        "current_section_content_raw": [],
        "current_option": None,
        "current_desc_lines": [],
        "in_options": False,
        "in_other_section": False,
    }

    for line in lines:
        line_stripped = line.strip()

        if line_stripped.endswith(":") and not line_stripped.startswith("-"):
            state = handle_section_header(
                state, line_stripped, section_raw_lines, options, additional_sections
            )
            continue

        if state["in_options"]:
            state["current_option"], state["current_desc_lines"] = process_option_line(
                line, line_stripped, state["current_option"], 
                state["current_desc_lines"], options
            )
        elif state["in_other_section"]:
            state["current_section_content"].append(line)
            state["current_section_content_raw"].append(line)
        else:
            if line_stripped and not line_stripped.startswith(
                ("usage", "options", "optional arguments")
            ):
                state["current_section_content"].append(line)

    if state["current_section"] is not None:
        if state["current_section"] in ("options", "optional arguments"):
            if state["current_option"] is not None:
                options.append(finalize_option(
                    state["current_option"], state["current_desc_lines"]
                ))
        else:
            if state["current_section_content"]:
                additional_sections.append(
                    finalize_section(
                        state["current_section"],
                        state["current_section_content"],
                        state["current_section_content_raw"],
                        section_raw_lines,
                    )
                )

    additional_text = collect_additional_text(lines, overview, section_raw_lines)
    if additional_text:
        additional_sections.append({"title": "additional_info", "content": additional_text})

    return options, additional_sections


def synthesize_top_level_node(command, parser):
    """Build node for top-level command from parser."""
    help_text = ""
    try:
        subparsers = get_subparsers(parser)
        for sp in subparsers:
            if command in sp.choices:
                help_text = sp.choices[command].format_help()
                break
    except Exception:
        pass

    lines = help_text.splitlines()
    usage, overview = extract_usage_and_overview(lines, command)
    options, additional_sections = parse_help_sections(lines, overview)

    return {
        "key": f"maas {command}",
        "argv": [command],
        "usage": usage,
        "options": options,
        "children": [],
        "overview": overview,
        "example": "",
        "keywords_text": "",
        "accepts_json": False,
        "returns_json": False,
        "additional_sections": additional_sections,
    }


def discover_top_level_from_parser(parser):
    """Discover top-level commands from parser."""
    commands = []
    subparsers = get_subparsers(parser)
    for sp in subparsers:
        for name in sp.choices.keys():
            if (
                name.replace("-", "").isalnum()
                and len(name) > 1
                and not name.startswith(("-", "--"))
                and name not in commands
            ):
                commands.append(name)
    return commands


def main():
    """Main entry point for CLI introspection."""
    add_repo_src_to_path()
    try:
        parser = build_parser()
    except Exception:
        return 2

    try_register_api_profile(parser)

    root_path = ["maas"]
    root = walk(parser, root_path)
    items = flatten(root)

    top_level_commands = discover_top_level_from_parser(parser)
    items = [it for it in items if len(it.get("argv", [])) != 1]

    for cmd in top_level_commands:
        items.append(synthesize_top_level_node(cmd, parser))

    json.dump(items, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
