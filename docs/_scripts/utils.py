# Copyright 2026 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


from pathlib import Path
import sys


# TODO: Ideally we should just install MAAS as a package instead
# during docs generation. Unclear if this will lead to lots of
# dependency issues and/or bloat, so preserving this way instead.
def add_repo_src_to_path():
    """Add repository src directory to Python path.

    Assumes the root of the repo is being tracked by git, and that it
    is the first parent that is so.
    """
    project_root = next(
        (
            parent
            for parent in Path(__file__).parents
            if (parent / ".git").exists()
        ),
        None,
    )
    if project_root is None:
        raise Exception(
            "root of the project was not found... is your MAAS repo not being tracked by git?"
        )

    src_dir = project_root / "src"
    if src_dir.is_dir() and src_dir not in sys.path:
        sys.path.insert(0, str(src_dir))
