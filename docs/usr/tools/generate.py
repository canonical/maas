#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Generate MAAS CLI documentation from introspector JSON."""

import argparse
import json
import re
import sys
from pathlib import Path

try:
    from jinja2 import Environment, FileSystemLoader, select_autoescape
except Exception:
    Environment = None
    FileSystemLoader = None
    select_autoescape = None


positional_arg_descriptions = {
    "system_id": "The system ID of the machine/device (e.g., `abc123`)",
    "id": "The ID of the resource (e.g., `1`, `abc123`)",
    "name": "The name of the resource (e.g., `my-machine`, `my-zone`)",
    "data ...": "Additional settings you can add (e.g., `architecture=amd64 hostname=my-machine`)",
}

run_modes_excluded_prefixes = [
    "{",
    "}",
    "When installing",
    "If you want",
    "sudo",
    "PostgreSQL",
    "this",
    "-h",
]

positional_args_excluded_prefixes = [
    "{",
    "}",
    "-",
]

top_level = {
    "login",
    "logout",
    "list",
    "refresh",
    "configauth",
    "apikey",
    "changepassword",
    "config-tls",
    "config-vault",
    "createadmin",
    "msm",
    "status",
    "init",
    "config",
    "migrate",
}


def normalize_period_spacing(text):
    """Normalize spacing after periods to single space."""
    return re.sub(r'\.\s{2,}', '. ', text)


def fix_ellipsis(text):
    """Replace '...' with proper ellipsis symbol '…'."""
    return re.sub(r'\.\.\.(?!\w)', '…', text)


def fix_lexical_illusions(text):
    """Remove repeated words (lexical illusions)."""
    text = re.sub(r'(\d+)\*(\d+)\*(\d+)', r'\1 * \2 * \3', text)
    if re.search(r'[*+\-=/]\s*\d+\s*[*+\-=/]', text):
        return text
    text = re.sub(r'\bOptional\s+\w+\.\s+Optional\.\s+Optional\s+', 
                  lambda m: m.group(0).replace(' Optional. Optional ', ' '), text, flags=re.IGNORECASE)
    text = re.sub(r'\bOptional\s+\w+\.\s+Optional\.\s+Optional\b', 
                  lambda m: m.group(0).replace(' Optional. Optional', ''), text, flags=re.IGNORECASE)
    text = re.sub(r'\bOptional\s+\w+\.\s+Optional\.', 
                  lambda m: m.group(0).replace(' Optional.', ''), text, flags=re.IGNORECASE)
    text = re.sub(r'\bOptional\.\s+Optional\.', 'Optional.', text, flags=re.IGNORECASE)
    text = re.sub(r'\balso\s+also\b', 'also', text, flags=re.IGNORECASE)
    text = re.sub(r'\band\s+and\b', 'and', text, flags=re.IGNORECASE)
    text = re.sub(r'\b(the|a|an|is|are|was|were)\s+\1\b', r'\1', text, flags=re.IGNORECASE)
    return text


def fix_curly_quotes(text):
    """Replace straight quotes with curly quotes."""
    if '<br>' in text or '`' not in text:
        left_quote = "\u201C"
        right_quote = "\u201D"
        text = re.sub(r'"([a-zA-Z0-9\-]+)"', left_quote + r'\1' + right_quote, text)
        text = re.sub(r'"(\d+-\w+)"', left_quote + r'\1' + right_quote, text)
    return text


def fix_weasel_words(text):
    """Remove or replace weasel words like 'very'."""
    return re.sub(r'\bvery\s+', '', text, flags=re.IGNORECASE)


def fix_common_misspellings(text):
    """Fix common misspellings found in generated documentation."""
    misspellings = {
        'intented': 'intended',
        'sensative': 'sensitive',
        'authorititative': 'authoritative',
        'conntected': 'connected',
        'freqeuncy': 'frequency',
        'inteface': 'interface',
        'adddress': 'address',
        'contoller': 'controller',
        'identifing': 'identifying',
        'seperated': 'separated',
        'specifed': 'specified',
        'assoicated': 'associated',
        'dimissing': 'dismissing',
        'transfered': 'transferred',
    }

    for wrong, correct in misspellings.items():
        text = re.sub(r'\b' + re.escape(wrong) + r'\b', correct, text, flags=re.IGNORECASE)

    return text


def apply_all_text_fixes(text):
    """Apply all text normalization fixes."""
    if not text:
        return ""
    text = normalize_period_spacing(text)
    text = fix_ellipsis(text)
    text = fix_lexical_illusions(text)
    text = fix_curly_quotes(text)
    text = fix_weasel_words(text)
    text = fix_common_misspellings(text)
    return text


def normalize_text(text):
    """Normalize text for Markdown output."""
    if not text:
        return ""
    text = re.sub(r"\r\n|\r|\n", "<br>", text.strip()).replace("|", "\\|")
    return apply_all_text_fixes(text)


def escape_md(text):
    """Escape markdown pipe characters."""
    if not text:
        return ""
    return text.replace('|', '\\|')


def bold_list_leaders(text):
    """Bold the leader word(s) in list items like "- Name: details"."""
    if not text:
        return text
    lines = text.splitlines()
    processed = []
    for ln in lines:
        stripped = ln.lstrip()
        indent = (m.group(0) if (m := re.match(r"^\s+", ln)) else "")
        if stripped.startswith("- ") and ":" in stripped:
            head, rest = stripped[2:].split(":", 1)
            head = head.strip()
            processed.append(f"{indent}- **{head}**:{rest}")
        else:
            processed.append(ln)
    return "\n".join(processed)


def parse_param_or_type_line(line, prefix):
    """Parse a :param or :type line, returning (name, value) or None if invalid."""
    if not line.startswith(prefix):
        return None
    try:
        after = line[len(prefix):]
        name, value = after.split(":", 1)
        return name.strip(), value.strip()
    except ValueError:
        return None


def collect_continuation_lines(lines, start_idx):
    """Collect continuation lines until next :param or :type, returning lines and next index."""
    collected = []
    j = start_idx + 1
    while j < len(lines):
        next_line = lines[j]
        next_stripped = next_line.strip()
        if next_stripped.startswith(":param ") or next_stripped.startswith(":type "):
            break
        collected.append(next_stripped)
        j += 1
    return collected, j


def format_keyword_text(text):
    """Format keyword text: escape markdown, replace sphinx-style references, convert newlines."""
    text = escape_md(text)
    text = re.sub(r"(?m)^:([a-z0-9_\-]+):", r"**:\1:**", text)
    text = apply_all_text_fixes(text)
    return "<br>".join(text.splitlines()) if text else ""


def bold_sphinx_directives(text):
    """Bold Sphinx-style directives like :name: without other formatting."""
    return re.sub(r"(?m)^:([a-z0-9_\-]+):", r"**:\1:**", text)


def should_blank_overview(overview):
    """Decide whether to blank out overview per formatting heuristic."""
    tmp = overview.replace("<br>", " ").strip()
    return bool(tmp and "." not in tmp and tmp.count(" "))


def has_positional_section(additional_sections):
    """Check if additional_sections contains a positional arguments section."""
    return any(
        isinstance(sec, dict)
        and str(sec.get("title", "")).strip().lower() == "positional arguments"
        for sec in additional_sections
    )


def is_sentence_fragment(sent, prev_sentences, index):
    """Check if a sentence is a fragment that should be removed."""
    sent_lower = sent.lower()
    for prev_sent in prev_sentences:
        prev_lower = prev_sent.lower()
        if sent_lower in prev_lower or prev_lower in sent_lower:
            if abs(len(sent_lower) - len(prev_lower)) > 10:
                return True
    if index > 0 and not sent[0].isupper():
        if re.match(r'^(mode|and|or|the|a|an|to|for|with|in|on|at)\s+', sent_lower):
            return True
    return False


def remove_duplicate_sentences(text):
    """Remove duplicate sentences and fragments from text."""
    sentences = re.split(r'\.\s+', text)
    seen = set()
    cleaned = []
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if not sent:
            continue
        sent_lower = sent.lower()
        if sent_lower not in seen and not is_sentence_fragment(sent, cleaned, i):
            seen.add(sent_lower)
            cleaned.append(sent)
    if cleaned:
        result = '. '.join(cleaned)
        if not result.endswith('.'):
            result += '.'
        return result.strip()
    return text


def normalize_options_list(options):
    """Normalize options rows and extract moved notes."""
    normalized = []
    moved_notes = []
    for row in options:
        opt_text = str(row.get("option", "")).rstrip()
        eff_text = str(row.get("effect", "")).strip()

        if "If credentials are not provided" in eff_text:
            moved_notes.append(
                "If credentials are not provided on the command-line, they will be prompted for interactively."
            )
            eff_text = eff_text.split("If credentials are not provided", 1)[0].rstrip()

        if eff_text:
            eff_text = apply_all_text_fixes(eff_text)
            eff_text = remove_duplicate_sentences(eff_text)

        if opt_text:
            normalized.append({"option": opt_text, "effect": eff_text})

    return normalized, moved_notes


def remove_optional_prefix(text):
    """Remove leading Optional/Required prefixes from descriptions."""
    while re.match(r'^(Optional|Required)\.\s+', text, flags=re.IGNORECASE):
        text = re.sub(r'^(Optional|Required)\.\s+', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^Optional\s+', '', text, flags=re.IGNORECASE)
    return text


def clean_lead_text(lead_lines, parsed_param_names):
    """Remove parsed :param/:type lines from lead text."""
    cleaned = []
    for line in lead_lines:
        line_stripped = line.strip()
        if line_stripped.startswith(":param "):
            parsed = parse_param_or_type_line(line_stripped, ":param ")
            if parsed and parsed[0] in parsed_param_names:
                continue
        if line_stripped.startswith(":type "):
            parsed = parse_param_or_type_line(line_stripped, ":type ")
            if parsed and parsed[0] in parsed_param_names:
                continue
        cleaned.append(line)
    lead = "\n".join(cleaned).strip()
    lead = re.sub(r'(:param\s+\w+:\s+(?:Optional|Required))\.\s{2,}', r'\1. ', lead, flags=re.IGNORECASE)
    lead = apply_all_text_fixes(lead)
    return format_keyword_text(lead)


def parse_param_line(lines, i, params, param_order, parsed_param_names):
    """Parse a :param line and return next index and current param name."""
    raw = lines[i]
    line = raw.strip()
    parsed = parse_param_or_type_line(line, ":param ")
    if parsed is None:
        return i + 1, None
    name, desc = parsed
    parsed_param_names.add(name)
    if name not in params:
        params[name] = {"name": name, "desc": "", "type": ""}
        param_order.append(name)
    entry = params[name]
    entry_desc_lines = [desc]
    continuation_lines, next_idx = collect_continuation_lines(lines, i)
    entry_desc_lines.extend(continuation_lines)
    desc_text = "\n".join(entry_desc_lines).strip()
    entry["desc"] = normalize_period_spacing(desc_text)
    return next_idx, name


def parse_type_line(line, params, param_order):
    """Parse a :type line. Returns True if parsed successfully."""
    parsed = parse_param_or_type_line(line, ":type ")
    if parsed is None:
        return False
    name, typ = parsed
    if name not in params:
        params[name] = {"name": name, "desc": "", "type": ""}
        param_order.append(name)
    params[name]["type"] = typ
    return True


def process_continuation_line(raw, current_param, params):
    """Process a continuation line for current parameter."""
    if re.match(r"^\s", raw):
        entry = params.get(current_param, {})
        desc_text = (entry.get("desc", "") + "\n" + raw.rstrip()).strip()
        entry["desc"] = normalize_period_spacing(desc_text)
        params[current_param] = entry
        return True
    return False


def parse_keywords_text(keywords_text):
    """Parse sphinx-style epilog into structured keywords."""
    result = {"lead": "", "params": []}
    if not keywords_text:
        return result

    lines = keywords_text.splitlines()
    lead_lines = []
    params = {}
    param_order = []
    current_param = None
    parsed_param_names = set()

    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.strip()

        if line.startswith(":param "):
            next_idx, param_name = parse_param_line(lines, i, params, param_order, parsed_param_names)
            if param_name:
                current_param = param_name
                i = next_idx
                continue
            lead_lines.append(raw)
            i += 1
        elif line.startswith(":type "):
            if parse_type_line(line, params, param_order):
                i += 1
                continue
            lead_lines.append(raw)
            i += 1
        else:
            if current_param is None:
                if line.startswith(":param "):
                    parsed = parse_param_or_type_line(line, ":param ")
                    if parsed and parsed[0] in parsed_param_names:
                        i += 1
                        continue
                lead_lines.append(raw)
            else:
                if not process_continuation_line(raw, current_param, params):
                    lead_lines.append(raw)
            i += 1

    ordered_params = [params[name] for name in param_order]
    lead = clean_lead_text(lead_lines, parsed_param_names)

    for e in ordered_params:
        desc_text = remove_optional_prefix(e.get("desc", "").strip())
        desc_text = apply_all_text_fixes(desc_text)
        e["desc"] = format_keyword_text(desc_text)
        e["type"] = escape_md(e.get("type", "")).strip()

    result["lead"] = lead
    result["params"] = ordered_params
    return result


def format_usage(usage, command_path):
    """Format usage string for Markdown."""
    if not usage:
        parts = command_path.split()
        return f"maas {' '.join(parts)} [-h]"

    usage = re.sub(r"^\s*usage\s*:?\s*", "", usage)
    markers = [
        " positional arguments:",
        " options:",
        " optional arguments:",
        " Keywords",
        " Command-line options",
    ]
    for marker in markers:
        idx = usage.find(marker)
        if idx != -1:
            usage = usage[:idx].rstrip()

    parts = command_path.split()
    if parts and parts[0] in top_level:
        return usage

    usage_parts = usage.split()
    if len(usage_parts) > 1 and usage_parts[0] == "maas":
        usage_parts[1] = "$PROFILE"
        usage = " ".join(usage_parts)

    return usage


def format_options(options):
    """Format command options as a Markdown table."""
    if not options:
        return ""

    lines = []
    lines.append("#### Command-line options")
    lines.append("| Option | Effect |")
    lines.append("|---|---|")
    for row in options:
        opt_text = str(row.get("option", "")).strip()
        eff_text = str(row.get("effect", "")).strip()
        lines.append(f"| {opt_text} | {eff_text} |")
    lines.append("")
    return "\n".join(lines)


def extract_positional_args(usage, command_path):
    """Extract positional arguments from usage."""
    if not usage:
        return []
    parts = command_path.split()
    if len(parts) == 1 and parts[0] in top_level:
        return []
    scrubbed = re.sub(r"\[[^\]]*\]", "", usage)
    tokens = scrubbed.split()
    if not tokens:
        return []
    if tokens and tokens[0] == "maas":
        tokens.pop(0)
    if tokens and tokens[0] == "$PROFILE":
        tokens.pop(0)
    path_tokens = command_path.split()
    i = 0
    for pt in path_tokens:
        if i < len(tokens) and tokens[i] == pt:
            i += 1
    tokens = tokens[i:]
    return [
        t.strip(",|")
        for t in tokens
        if t not in {"...", "COMMAND", "|"}
        and "{" not in t
        and "}" not in t
    ]


def format_positional_args(args):
    """Format positional arguments as Markdown table."""
    if not args:
        return ""

    markdown = "#### Positional arguments\n"
    markdown += "| Argument | Effect |\n"
    markdown += "|----------|--------|\n"

    for arg in args:
        description = positional_arg_descriptions.get(
            arg, f"The {arg} parameter"
        )

        markdown += f"| {arg} | {description} |\n"

    markdown += "\n"
    return markdown


def is_malformed_content(content):
    """Check if content looks like malformed concatenated text."""
    if re.match(r'^\[--[\w-]+', content.strip()):
        return True
    if len(content) > 500 and not any(marker in content for marker in ['. ', '.\n', '<br>', '\n\n']):
        return True
    return False


def clean_additional_sections(additional_sections):
    """Filter and clean additional sections."""
    cleaned = []
    for sec in additional_sections:
        if isinstance(sec, dict) and isinstance(sec.get("content"), str):
            content = sec["content"]
            if sec.get("title") == "additional_info" and is_malformed_content(content):
                continue
            content = apply_all_text_fixes(content)
            sec["content"] = bold_list_leaders(content)
            if sec["content"].strip():
                cleaned.append(sec)
        else:
            cleaned.append(sec)
    return cleaned


def render_with_template(env, context):
    """Render template with context."""
    template = env.get_template("cli_page.md.j2")
    return template.render(**context)


def generate_command_markdown(env, command, command_path):
    """Generate Markdown content for a single command using Jinja2."""
    overview_raw = command.get("overview", "") or ""
    overview_lines = [
        ln
        for ln in overview_raw.splitlines()
        if not ln.strip().lower().startswith("cli help for:")
    ]
    overview = normalize_text("\n".join(overview_lines))
    if overview and overview.endswith("<br>") and should_blank_overview(overview):
        overview = ""
    usage_raw = command.get("usage", "")
    options = command.get("options", [])
    keywords_text = command.get("keywords_text", "")
    keywords = parse_keywords_text(keywords_text)
    
    usage = format_usage(usage_raw, command_path)
    if overview_lines:
        ov_line = overview_lines[0].strip()
        if ov_line and usage.endswith(ov_line):
            usage = usage[: -len(ov_line)].rstrip()

    additional_sections = command.get("additional_sections", [])
    has_pos_section = has_positional_section(additional_sections)
    positional_args = (
        []
        if has_pos_section
        else extract_positional_args(usage, command_path)
    )

    if (not has_pos_section) and not positional_args and overview:
        token_only = re.match(
            r"^[a-z_][a-z0-9_]*(\s+[a-z_][a-z0-9_]*)+$",
            overview.replace("<br>", " "),
        )
        if token_only and len(command_path.split()) >= 2:
            positional_args = overview.replace("<br>", " ").split()
            overview = ""

    normalized_options, moved_notes = normalize_options_list(options)

    if moved_notes:
        additional_sections.append(
            {"title": "additional_info", "content": "\n".join(moved_notes)}
        )

    if keywords_text and not (keywords.get("params") or keywords.get("lead")):
        keywords_text = apply_all_text_fixes(keywords_text)
        keywords_text = bold_sphinx_directives(keywords_text)
    else:
        keywords_text = ""

    additional_sections = clean_additional_sections(additional_sections)

    context = {
        "overview": overview,
        "usage": usage,
        "positional_args": positional_args,
        "positional_arg_descriptions": positional_arg_descriptions,
        "run_modes_excluded_prefixes": run_modes_excluded_prefixes,
        "positional_args_excluded_prefixes": positional_args_excluded_prefixes,
        "options": normalized_options,
        "keywords_text": keywords_text,
        "keywords": keywords,
        "accepts_json": bool(command.get("accepts_json", False)),
        "returns_json": bool(command.get("returns_json", False)),
        "additional_sections": additional_sections,
    }
    return render_with_template(env, context)


def path_to_filename(path):
    """Convert command path to filename."""
    return path.replace(" ", "-").lower() + ".md"


def pluralize_for_filename(base_name):
    """Convert singular filename to plural form for lookup."""
    plural_map = {
        'commissioning-script': 'commissioning-scripts',
        'event': 'events',
        'ipaddress': 'ipaddresses',
        'node-result': 'node-results',
        'vmfs-datastore': 'vmfs-datastores',
    }
    return plural_map.get(base_name, base_name)


def find_existing_topic_number(base_name, output_dir):
    """Find existing file with topic number or return None."""
    if not output_dir.exists():
        return None, None

    search_names = [base_name]
    plural_name = pluralize_for_filename(base_name)
    if plural_name != base_name:
        search_names.append(plural_name)

    for search_name in search_names:
        pattern = re.compile(rf"^{re.escape(search_name)}-(\d+).md$")
        tba_pattern = re.compile(rf"^{re.escape(search_name)}-tba.md$")

        for file in output_dir.glob("**/*.md"):
            filename = file.name
            if m := pattern.match(filename):
                return m.group(1), search_name
            if tba_pattern.match(filename):
                return "tba", search_name

    return None, None


def singularize_resource(resource):
    """Singularize a CLI resource token."""
    curated = {
        "machines": "machine",
        "nodes": "node",
        "subnets": "subnet",
        "fabrics": "fabric",
        "vlans": "vlan",
        "spaces": "space",
        "tags": "tag",
        "users": "user",
        "zones": "zone",
        "resource-pools": "resource-pool",
        "interfaces": "interface",
        "ipranges": "iprange",
        "ipaddresses": "ipaddress",
        "files": "file",
        "partitions": "partition",
        "block-devices": "block-device",
        "raid": "raid",
        "bcaches": "bcache",
        "vm-hosts": "vm-host",
        "vm-clusters": "vm-cluster",
        "boot-resources": "boot-resource",
        "boot-sources": "boot-source",
        "devices": "device",
        "node-devices": "node-device",
        "discoveries": "discovery",
        "dnsresources": "dnsresource",
        "static-routes": "static-route",
        "package-repositories": "package-repository",
        "vmfs-datastores": "vmfs-datastore",
        "volume-groups": "volume-group",
        "rack-controllers": "rack-controller",
        "region-controllers": "region-controller",
        "maas": "maas",
    }
    if resource in curated:
        return curated[resource]

    if "-" in resource and resource.endswith("s"):
        return resource[:-1]

    if resource.endswith("es") and len(resource) > 3:
        return resource[:-2]
    if resource.endswith("s") and len(resource) > 2:
        return resource[:-1]
    return resource


def parse_key_to_group(key):
    """Return (group_name, command_path_for_usage)."""
    parts = key.split()
    if len(parts) >= 3 and parts[0] == "maas":
        if len(parts) >= 4:
            resource = parts[2]
            group = singularize_resource(resource)
            command_path = " ".join(parts[2:])
            return group, command_path
        if len(parts) == 3:
            top = parts[1]
            command_path = " ".join(parts[1:])
            return top, command_path
        if len(parts) == 2:
            return parts[1], parts[1]
    fallback = (
        " ".join(parts[1:]) if parts and parts[0] == "maas" else key
    )
    return fallback or key, fallback or key


def group_commands_by_resource(commands):
    """Group commands by resource base (singular), or by top-level cmd."""
    groups = {}
    for cmd in commands:
        key = str(cmd.get("key", ""))
        group, command_path = parse_key_to_group(key)
        groups.setdefault(group, []).append((cmd, command_path or group))
    return groups


def main():
    parser = argparse.ArgumentParser(
        description="Generate MAAS CLI documentation from introspector JSON"
    )
    parser.add_argument(
        "--stdin",
        action="store_true",
        help="Read introspector JSON array from stdin",
    )
    parser.add_argument(
        "--source", help="Optional path to JSON file (array of nodes)"
    )
    parser.add_argument(
        "--out", required=True, help="Output directory for Markdown files"
    )
    parser.add_argument(
        "--check-dirty",
        action="store_true",
        help="Exit nonzero if any file would change",
    )
    parser.add_argument(
        "--template-dir",
        default="docs/usr/tools",
        help="Directory containing cli_page.md.j2",
    )
    args = parser.parse_args()

    nodes = []
    try:
        if args.stdin:
            nodes = json.load(sys.stdin)
        elif args.source:
            with open(args.source, "r", encoding="utf-8") as f:
                nodes = json.load(f)
        else:
            print("Error: Provide --stdin or --source", file=sys.stderr)
            return 2
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON: {e}", file=sys.stderr)
        return 1

    if not isinstance(nodes, list) or not nodes:
        print("Warning: No commands found in input", file=sys.stderr)
        return 0

    output_dir = Path(args.out)
    output_dir.mkdir(parents=True, exist_ok=True)

    if Environment is None:
        print("Error: Jinja2 is required to render templates.", file=sys.stderr)
        return 1
    env = Environment(
        loader=FileSystemLoader(args.template_dir),
        autoescape=select_autoescape(enabled_extensions=(".j2",)),
        trim_blocks=True,
        lstrip_blocks=True,
    )

    seen_keys = {}
    for node in nodes:
        k = str(node.get("key", ""))
        if not k:
            continue
        seen_keys[k] = node
    unique_commands = [
        seen_keys[k] for k in sorted(seen_keys.keys())
    ]

    groups = group_commands_by_resource(unique_commands)

    files_created = 0
    files_updated = 0
    files_skipped = 0
    files_would_change = 0

    groups_to_skip = {"local", "admin"}

    for group_name, cmd_list in sorted(groups.items()):
        if group_name in groups_to_skip:
            continue

        filename = (
            f"{group_name}.md"
            if " " not in group_name
            else path_to_filename(group_name)
        )

        base_name = filename.replace(".md", "")
        suffix, actual_base_name = find_existing_topic_number(
            base_name, output_dir
        )
        if suffix and actual_base_name:
            filename = f"{actual_base_name}-{suffix}.md"
        else:
            filename = f"{base_name}-tba.md"

        filepath = output_dir / filename

        markdown_parts = []
        for command, command_path in sorted(
            cmd_list, key=lambda t: (t[1], str(t[0].get("key", "")))
        ):
            markdown_parts.append(
                generate_command_markdown(env, command, command_path)
            )
            markdown_parts.append("")
        markdown_content = "\n".join(markdown_parts).rstrip() + "\n"

        if filepath.exists():
            with open(filepath, "r", encoding="utf-8") as f:
                existing_content = f.read()
            if existing_content == markdown_content:
                files_skipped += 1
            else:
                files_updated += 1
                files_would_change += 1
                if not args.check_dirty:
                    with open(filepath, "w", encoding="utf-8") as wf:
                        wf.write(markdown_content)
        else:
            files_created += 1
            files_would_change += 1
            if not args.check_dirty:
                with open(filepath, "w", encoding="utf-8") as wf:
                    wf.write(markdown_content)

    print(f"Documentation generation completed!")
    print(f"Output directory: {output_dir}")
    print(f"Files created: {files_created}")
    print(f"Files updated: {files_updated}")
    print(f"Files skipped: {files_skipped}")
    print(f"Total commands processed: {len(unique_commands)}")

    if args.check_dirty and files_would_change:
        return 3
    return 0


if __name__ == "__main__":
    exit(main())