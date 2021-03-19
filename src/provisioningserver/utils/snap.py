# Copyright 2016 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Snap utilities."""

import os
from pathlib import Path

import yaml


def running_in_snap():
    """Return True if running in a snap."""
    return "SNAP" in os.environ


def get_snap_path():
    """Return the path into the snap."""
    return os.environ.get("SNAP", None)


def get_snap_data_path():
    """Return the path to snap data."""
    return os.environ.get("SNAP_DATA", None)


def get_snap_common_path():
    """Return the path to snap common."""
    return os.environ.get("SNAP_COMMON", None)


def get_snap_version():
    """Return the version string in the snap metadata."""
    snap_path = get_snap_path()
    if snap_path is None:
        return None
    meta_path = os.path.join(snap_path, "meta", "snap.yaml")
    with open(meta_path, "r") as fp:
        snap_meta = yaml.safe_load(fp)
    return snap_meta["version"]


def get_snap_mode():
    """Return the snap mode."""
    path = Path(get_snap_common_path()) / "snap_mode"
    if not path.exists():
        return None
    mode = path.read_text().strip()
    if mode == "none":
        return None
    return mode
