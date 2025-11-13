#!/usr/bin/env python3
# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Publish generated Markdown documentation to Discourse topics."""

import argparse
import os
import re
import sys
import time
from pathlib import Path
from typing import Dict

THIS_DIR = Path(__file__).parent
sys.path.insert(0, str(THIS_DIR))

try:
    from discourse_api import DiscourseAPI  # noqa: E402
except ImportError as e:
    print(f"Error: Could not import discourse_api module: {e}", file=sys.stderr)
    print("Ensure discourse_api.py is in the same directory", file=sys.stderr)
    sys.exit(1)


def infer_mapping_from_filenames(docs_dir: Path) -> Dict[str, int]:
    """Infer topic mapping by parsing Markdown filenames with trailing IDs."""
    mapping: Dict[str, int] = {}
    pattern = re.compile(r"-(\d+)\.md$")

    for path in sorted(docs_dir.glob("*.md")):
        if m := pattern.search(path.name):
            mapping[path.name] = int(m.group(1))

    if not mapping:
        raise SystemExit(
            f"Error: Could not infer any topic IDs from filenames in "
            f"{docs_dir}"
        )

    return mapping


def load_markdown_content(docs_dir: Path, filename: str) -> str:
    """Load Markdown content from a file."""
    file_path = (docs_dir / filename).resolve()

    if not file_path.is_file():
        raise FileNotFoundError(f"Markdown file not found: {file_path}")

    try:
        return file_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as e:
        raise UnicodeDecodeError(
            f"Could not decode {file_path} as UTF-8: {e}"
        )


def update_topic_content(
    api: DiscourseAPI,
    topic_id: int,
    content: str,
    dry_run: bool = False,
) -> bool:
    """Update a Discourse topic with new content."""
    if dry_run:
        print(
            f"[DRY-RUN] Would update topic {topic_id} ({len(content)} bytes)"
        )
        return True

    try:
        current_content = api.get_markdown(topic_id)

        if current_content == content:
            print(f"[SKIP] No changes needed for topic {topic_id}")
            return False

        api.update_topic_content(topic_id, content)
        print(f"[UPDATE] Successfully updated topic {topic_id}")
        return True

    except Exception as e:
        raise SystemExit(f"Error updating topic {topic_id}: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish generated CLI documentation to Discourse topics",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  DISCOURSE_BASE_URL    Base URL of the Discourse instance
  DISCOURSE_API_KEY     API key for authentication

Examples:
  python3 publish_to_discourse.py --dry-run
  python3 publish_to_discourse.py --docs-dir /path/to/markdown
        """,
    )

    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=Path("docs/usr/markdown"),
        help="Directory containing generated Markdown files",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be updated without making changes",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose output for debugging",
    )

    args = parser.parse_args()

    base_url = os.getenv("DISCOURSE_BASE_URL")
    api_key = os.getenv("DISCOURSE_API_KEY")

    if not base_url:
        print(
            "Error: DISCOURSE_BASE_URL environment variable is required",
            file=sys.stderr,
        )
        print(
            "Set it to your Discourse instance URL (e.g., "
            "https://discourse.maas.io)",
            file=sys.stderr,
        )
        return 2

    if not api_key:
        print(
            "Error: DISCOURSE_API_KEY environment variable is required",
            file=sys.stderr,
        )
        print(
            "Get an API key from your Discourse user preferences",
            file=sys.stderr,
        )
        return 2

    base_url = base_url.rstrip("/")

    if args.verbose:
        print(f"Discourse URL: {base_url}")
        print(f"API Key: {'*' * len(api_key)}")
        print(f"Docs directory: {args.docs_dir}")
        print(f"Dry run: {args.dry_run}")

    if not args.docs_dir.exists():
        print(
            f"Error: Docs directory does not exist: {args.docs_dir}",
            file=sys.stderr,
        )
        return 1

    if not args.docs_dir.is_dir():
        print(
            f"Error: Docs path is not a directory: {args.docs_dir}",
            file=sys.stderr,
        )
        return 1

    try:
        mapping = infer_mapping_from_filenames(args.docs_dir)
        if args.verbose:
            print(f"Inferred {len(mapping)} topic mappings from filenames")
    except SystemExit as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    try:
        api = DiscourseAPI({"base_url": base_url, "api_key": api_key})
    except Exception as e:
        print(f"Error initializing Discourse API: {e}", file=sys.stderr)
        return 1

    start_time = time.time()
    updated_count = 0
    skipped_count = 0
    error_count = 0

    print(f"Processing {len(mapping)} topic mappings...")
    if args.dry_run:
        print("DRY RUN MODE - No changes will be made")

    for filename, topic_id in mapping.items():
        try:
            content = load_markdown_content(args.docs_dir, filename)

            if args.verbose:
                print(f"Processing {filename} -> topic {topic_id}")

            was_updated = update_topic_content(
                api, topic_id, content, args.dry_run
            )

            if was_updated:
                updated_count += 1
            else:
                skipped_count += 1

        except SystemExit as e:
            print(
                f"Fatal error processing {filename}: {e}", file=sys.stderr
            )
            error_count += 1
        except Exception as e:
            print(f"Error processing {filename}: {e}", file=sys.stderr)
            error_count += 1

    duration = time.time() - start_time

    print("\n" + "=" * 50)
    print("PUBLISHING SUMMARY")
    print("=" * 50)
    print(f"Total files processed: {len(mapping)}")
    print(f"Successfully updated: {updated_count}")
    print(f"Skipped (no changes): {skipped_count}")
    print(f"Errors: {error_count}")
    print(f"Duration: {duration:.1f} seconds")

    if args.dry_run:
        print("\nThis was a dry run - no actual changes were made")

    if error_count > 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())