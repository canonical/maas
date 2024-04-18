# Copyright 2012-2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Manage enrol requests with a Site Manager instance"""


def msm_enrol(jwt: str, metainfo: str | None = None) -> None:
    """Send enrolment request.

    Args:
        jwt (str): the enrolment token
        metainfo (str | None, optional): Additional site information. Defaults to None.
    """
    return None


def msm_withdraw() -> None:
    """Withdraw from MSM."""
    return None


def msm_status() -> tuple[str | None, bool]:
    """Get MSM connection status.

    Returns:
        tuple[str | None, bool]: a tuple of MSM URL and whether a connection is
        currently established. When MAAS is not enroled to MSM, it returns
        `(None, False)`
    """
    return (None, False)
