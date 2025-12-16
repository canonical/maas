# Copyright 2025 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).


def human_readable_bytes(num_bytes: int | float, include_suffix=True) -> str:  # pyright: ignore[reportReturnType]
    """Return the human readable text for bytes. (SI units)

    :param num_bytes: Bytes to be converted. Can't be None
    :param include_suffix: Whether to include the computed suffix in the
        output.
    """
    # Case is important: 1kB is 1000 bytes, whereas 1KB is 1024 bytes. See
    # https://en.wikipedia.org/wiki/Byte#Unit_symbol
    for unit in ["bytes", "kB", "MB", "GB", "TB", "PB", "EB", "ZB", "YB"]:
        if abs(num_bytes) < 1000.0 or unit == "YB":
            if include_suffix:
                if unit == "bytes":
                    return f"{num_bytes:.0f} {unit}"
                else:
                    return f"{num_bytes:.1f} {unit}"
            else:
                if unit == "bytes":
                    return "%.0f" % num_bytes
                else:
                    return "%.1f" % num_bytes
        num_bytes /= 1000.0
