#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Discover MAAS CLI commands by constructing argparse tree from source."""

import argparse
import json
import os
import re
import subprocess
import sys
from typing import Any, Dict, List, Set

try:
    import importlib.metadata as _ilm
except ImportError:
    _ilm = None


def eprint(msg: str) -> None:
    sys.stderr.write(msg + "\n")
# Compiled regexes (shared)
USAGE_LINE_RE = re.compile(r"^usage\s*:?", re.IGNORECASE)
OPT_DESC_RE = re.compile(r"^(?P<opt>\S.*?\S)\s{2,}(?P<desc>.+)$")
# Built-in top-level commands available without profiles
BUILTINS = {
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

# Commands to exclude from shell-discovered top-level list
PROFILE_COMMANDS = {"admin", "local"}



def add_repo_src_to_path() -> None:
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    src_dir = os.path.join(repo_root, "src")
    if os.path.isdir(src_dir) and src_dir not in sys.path:
        sys.path.insert(0, src_dir)
        eprint(f"[introspect] Using repo src: {src_dir}")


def build_parser(argv0: str = "maas") -> argparse.ArgumentParser:
    if _ilm is not None:
        _orig_distribution = getattr(_ilm, "distribution", None)

        def _fake_distribution(name: str):
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
            eprint(
                "[introspect] Patched importlib.metadata.distribution "
                "for 'maas'"
            )

    from maascli.parser import prepare_parser

    fake_argv = [argv0]
    parser = prepare_parser(fake_argv)
    eprint("[introspect] Parser constructed via maascli.parser.prepare_parser")
    return parser


def try_register_api_profile(
    parser: argparse.ArgumentParser,
) -> bool:
    """Synthesize profile from API describe/ if no profiles configured."""
    try:
        from maascli.api import (
            fetch_api_description,
            register_resources,
            profile_help,
        )

        # If profiles already exist, nothing to do.
        has_profile = False
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                for name in action.choices.keys():
                    if name not in BUILTINS:
                        has_profile = True
                        break
        if has_profile:
            eprint(
                "[introspect] Profiles already registered; "
                "skipping synthetic API profile"
            )
            return True

        from maascli.utils import api_url as _normalize_api_url

        base_url = os.environ.get(
            "MAAS_INTROSPECT_URL", "http://localhost:5240/MAAS/"
        )
        api_base = _normalize_api_url(base_url)
        eprint(
            f"[introspect] Fetching API description from: "
            f"{api_base}describe/"
        )
        description = fetch_api_description(api_base)

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
        eprint(
            "[introspect] Synthetic profile 'local' registered from "
            "API describe"
        )
        return True
    except Exception as exc:
        eprint(
            f"[introspect] Could not register synthetic API profile: {exc}"
        )
        return False


def get_subparsers(
    parser: argparse.ArgumentParser,
) -> List[argparse._SubParsersAction]:
    subparsers: List[argparse._SubParsersAction] = []
    for action in parser._actions:
        if isinstance(action, argparse._SubParsersAction):
            subparsers.append(action)
    return subparsers


def collect_optional_rows(
    parser: argparse.ArgumentParser,
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for action in parser._get_optional_actions():
        if not getattr(action, "option_strings", None):
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
        help_text = getattr(action, "help", None) or ""
        help_text = str(help_text)
        # Escape pipes and normalize whitespace/newlines once
        help_text = help_text.replace("|", r"\|")
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


def node_key(path: List[str]) -> str:
    return " ".join(path)


def describe_parser(
    parser: argparse.ArgumentParser, path: List[str]
) -> Dict[str, Any]:
    usage = parser.format_usage().strip()
    description = parser.description or ""
    epilog = parser.epilog or ""

    accepts_json = ":param" in (epilog or "")
    returns_json = False

    additional_sections = []
    if len(path) == 2 and path[0] == "maas":
        command = path[1]
        try:
            proc = subprocess.run(
                ["maas", command, "-h"],
                check=True,
                capture_output=True,
                text=True,
            )
            help_text = proc.stdout or proc.stderr or ""

            lines = help_text.splitlines()
            current_section = None
            current_section_content = []

            for line in lines:
                s = line.strip()
                if (
                    s.endswith(":")
                    and not s.startswith("-")
                    and s
                    not in ["usage:", "options:", "optional arguments:"]
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
                    and not s.startswith(
                        ("usage", "options", "optional arguments")
                    )
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

        except Exception as exc:
            eprint(
                f"[introspect] Could not get additional sections for "
                f"'maas {command}': {exc}"
            )

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


def walk(
    parser: argparse.ArgumentParser, path: List[str]
) -> Dict[str, Any]:
    node = describe_parser(parser, path)
    subparsers = get_subparsers(parser)
    total_children = 0
    for sp in subparsers:
        for name, subparser in sorted(sp.choices.items()):
            child_path = path + [name]
            eprint(f"[introspect] Descend: {' '.join(child_path)}")
            child_node = walk(subparser, child_path)
            node["children"].append(child_node)
            total_children += 1
    if total_children == 0:
        eprint(f"[introspect] Leaf: {' '.join(path)}")
    return node


def flatten(node: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = [
        {k: v for k, v in node.items() if k != "children"}
    ]
    for c in node.get("children", []):
        out.extend(flatten(c))
    return out


def _normalize_drill_down(content: List[str]) -> str:
    entries: List[str] = []
    i = 0
    while i < len(content):
        t0 = content[i].strip()
        if not t0 or t0 == "COMMAND":
            i += 1
            continue
        if "  " in t0:
            entries.append(t0)
            i += 1
            continue
        desc = ""
        if i + 1 < len(content):
            nxt = content[i + 1]
            if nxt.startswith(" ") or nxt.startswith("\t"):
                desc = nxt.strip()
                i += 2
            else:
                i += 1
        else:
            i += 1
        if desc:
            entries.append(f"{t0}  {desc}")
        else:
            entries.append(t0)
    return "\n".join(entries)


def _normalize_positional_args(content: List[str]) -> str:
    entries: List[str] = []
    # Join all content into a single string for processing
    full_text = " ".join(line.strip() for line in content if line.strip())
    
    # Find all argument boundaries: word followed by 2+ spaces
    matches = list(re.finditer(r'(\S+)\s{2,}', full_text))
    
    if len(matches) > 1:
        # Multiple args on one line - parse them
        for i, match in enumerate(matches):
            arg_name = match.group(1)
            desc_start = match.end()
            desc_end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
            desc = full_text[desc_start:desc_end].strip()
            # Remove trailing period if it's clearly separating from next arg
            if desc.endswith(".") and i + 1 < len(matches):
                desc = desc[:-1].strip()
            if desc:
                entries.append(f"{arg_name}  {desc}")
            else:
                entries.append(arg_name)
    else:
        # Original single-arg-per-line logic or single arg
        i = 0
        while i < len(content):
            head = content[i]
            head_stripped = head.strip()
            name = head_stripped
            first_desc = ""
            m = re.match(
                r"^(?P<name>\S.*?)\s{2,}(?P<desc>.+)$", head_stripped
            )
            if m:
                name = m.group("name").strip()
                first_desc = m.group("desc").strip()
            if not name:
                i += 1
                continue
            desc_parts: List[str] = []
            if first_desc:
                desc_parts.append(first_desc)
            j = i + 1
            while j < len(content):
                nxt = content[j]
                if nxt.startswith(" ") or nxt.startswith("\t"):
                    desc_parts.append(nxt.strip())
                    j += 1
                else:
                    break
            desc = " ".join(desc_parts).strip()
            if desc:
                entries.append(f"{name}  {desc}")
            else:
                entries.append(name)
            i = j
    
    return "\n".join(entries)


def synthesize_top_level_node(command: str) -> Dict[str, Any]:
    """Build node for top-level command by running 'maas <cmd> -h'."""
    help_text = ""
    try:
        proc = subprocess.run(
            ["maas", command, "-h"],
            check=True,
            capture_output=True,
            text=True,
        )
        help_text = proc.stdout or proc.stderr or ""
    except Exception as exc:
        eprint(f"[introspect] Could not shell 'maas {command} -h': {exc}")
        help_text = ""

    usage = ""
    overview = ""
    lines = help_text.splitlines()

    def _is_usage_line(s: str) -> bool:
        return USAGE_LINE_RE.match(s) is not None

    usage_lines = []
    in_usage = False
    for line in lines:
        s = line.strip()
        if _is_usage_line(s):
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

    if usage_lines:
        usage = " ".join(usage_lines)

    in_usage_section = False
    for line in lines:
        s = line.strip()
        if _is_usage_line(s):
            in_usage_section = True
            continue
        if in_usage_section and s and not s.startswith(
            ("usage", "options", "optional arguments", "[")
        ):
            overview = s
            break

    if not usage:
        usage = f"usage: maas {command} [-h]"
    if not overview:
        overview = f"CLI help for: maas {command} [-h]"

    options = []
    additional_sections = []
    current_section = None
    current_section_content = []
    current_section_content_raw: List[str] = []
    section_raw_lines: Set[str] = set()
    current_option = None
    current_desc_lines = []

    in_options = False
    in_other_section = False

    for line in lines:
        s = line.strip()

        if s.endswith(":") and not s.startswith("-"):
            if current_section is not None:
                if current_section in ("options", "optional arguments"):
                    if current_option is not None:
                        desc = " ".join(current_desc_lines).strip()
                        opt_text = current_option
                        if not desc:
                            if m := OPT_DESC_RE.match(opt_text):
                                opt_text = m.group("opt").strip()
                                desc = m.group("desc").strip()
                        options.append({"option": opt_text, "effect": desc})
                else:
                    if current_section_content:
                        content = "\n".join(current_section_content)
                        title_lower = current_section.strip().lower()
                        if title_lower == "drill down":
                            content = _normalize_drill_down(
                                current_section_content
                            )
                        elif title_lower == "positional arguments":
                            content = _normalize_positional_args(
                                current_section_content
                            )
                        additional_sections.append(
                            {"title": current_section, "content": content}
                        )

                    # Record raw lines from the section we just finished
                    for rl in current_section_content_raw:
                        section_raw_lines.add(rl.strip())
                    current_section = s.rstrip(":")
                    current_section_content = []
                    current_section_content_raw = []
            # Record raw lines from the previous section when switching
            if current_section_content_raw:
                for rl in current_section_content_raw:
                    section_raw_lines.add(rl.strip())
            current_section = s.rstrip(":")
            current_section_content = []
            current_section_content_raw = []
            current_option = None
            current_desc_lines = []

            if current_section in ("options", "optional arguments"):
                in_options = True
                in_other_section = False
            else:
                in_options = False
                in_other_section = True
            continue

        if in_options:
            if not s:
                continue
            if s.startswith("-"):
                if current_option is not None:
                    desc = " ".join(current_desc_lines).strip()
                    opt_text = current_option
                    # Check if option line itself contains description
                    if not desc:
                        m = re.match(
                            r"^(?P<opt>\S.*?\S)\s{2,}(?P<desc>.+)$", opt_text
                        )
                        if m:
                            opt_text = m.group("opt").strip()
                            desc = m.group("desc").strip()
                    options.append({"option": opt_text, "effect": desc})
                # Check if the new option line contains description
                if m := OPT_DESC_RE.match(s):
                    current_option = m.group("opt").strip()
                    current_desc_lines = [m.group("desc").strip()]
                else:
                    current_option = s
                    current_desc_lines = []
            elif current_option is not None:
                # Only treat indented lines as continuation of the option's description
                if line.startswith(" ") or line.startswith("\t"):
                    current_desc_lines.append(s)
        elif in_other_section:
            current_section_content.append(line)
            current_section_content_raw.append(line)
        else:
            if s and not s.startswith(
                ("usage", "options", "optional arguments")
            ):
                current_section_content.append(line)

    if current_section is not None:
        if current_section in ("options", "optional arguments"):
            if current_option is not None:
                desc = " ".join(current_desc_lines).strip()
                opt_text = current_option
                if not desc:
                    if m := OPT_DESC_RE.match(opt_text):
                        opt_text = m.group("opt").strip()
                        desc = m.group("desc").strip()
                options.append({"option": opt_text, "effect": desc})
        else:
            if current_section_content:
                content = "\n".join(current_section_content)
                title_lower = current_section.strip().lower()
                if title_lower == "drill down":
                    content = _normalize_drill_down(current_section_content)
                elif title_lower == "positional arguments":
                    content = _normalize_positional_args(
                        current_section_content
                    )
                additional_sections.append(
                    {"title": current_section, "content": content}
                )
            # Record raw lines from the final section
            if current_section_content_raw:
                for rl in current_section_content_raw:
                    section_raw_lines.add(rl.strip())

    additional_text = []
    for line in lines:
        s = line.strip()
        if (
            s
            and not s.startswith(("usage", "options", "optional arguments"))
            and not s.endswith(":")
        ):
            is_part_of_section = s in section_raw_lines
            # Skip option signature-style lines (already captured in options table)
            if not is_part_of_section and s != overview and not s.startswith(("-", "--")):
                additional_text.append(line)

    if additional_text:
        # Normalize prose into a single paragraph line
        extra = " ".join(l.strip() for l in additional_text if l.strip())
        extra = extra.replace("|", r"\|")
        additional_sections.append({"title": "additional_info", "content": extra})

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


def discover_top_level_from_shell() -> List[str]:
    """Parse 'maas -h' to discover available top-level commands."""
    try:
        proc = subprocess.run(
            ["maas", "-h"], check=True, capture_output=True, text=True
        )
        out = (proc.stdout or proc.stderr or "").splitlines()
    except Exception as exc:
        eprint(f"[introspect] Could not shell 'maas -h': {exc}")
        return []

    commands: List[str] = []
    in_drill_down = False

    for line in out:
        s = line.strip()

        if s.lower().startswith("drill down:"):
            in_drill_down = True
            continue

        if not in_drill_down:
            continue

        if not s or s.startswith("http"):
            break

        if line.startswith("    "):
            parts = s.split()
            if parts:
                cmd = parts[0]
                if (
                    cmd.replace("-", "").isalnum()
                    and len(cmd) > 1
                    and not cmd.startswith(("-", "--"))
                    and cmd not in {"COMMAND", "Change", "drill"}
                    and cmd not in commands
                ):
                    commands.append(cmd)

    return [cmd for cmd in commands if cmd not in PROFILE_COMMANDS]


def main() -> int:
    add_repo_src_to_path()
    try:
        parser = build_parser()
    except Exception as exc:
        eprint(f"[introspect] Failed to build parser: {exc}")
        return 2

    try_register_api_profile(parser)

    root_path = ["maas"]
    eprint("[introspect] Walking argparse tree...")
    root = walk(parser, root_path)

    items = flatten(root)
    eprint(f"[introspect] Commands discovered (nodes): {len(items)}")

    top_level_commands = discover_top_level_from_shell()
    eprint(
        f"[introspect] Top-level commands from shell: "
        f"{top_level_commands}"
    )

    before = len(items)
    items = [it for it in items if len(it.get("argv", [])) != 1]
    removed = before - len(items)
    eprint(
        f"[introspect] Removed {removed} argparse-derived top-level nodes"
    )

    for cmd in top_level_commands:
        eprint(
            f"[introspect] Synthesizing top-level '{cmd}' from shell help"
        )
        items.append(synthesize_top_level_node(cmd))

    json.dump(items, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


