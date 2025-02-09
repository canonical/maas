# Copyright 2018 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Syslog config management module."""

from operator import itemgetter
import os
import sys

import tempita

from provisioningserver.utils import locate_template, snap
from provisioningserver.utils.fs import atomic_write
from provisioningserver.utils.twisted import synchronous

MAAS_SYSLOG_CONF_NAME = "rsyslog.conf"
MAAS_SYSLOG_CONF_TEMPLATE = "rsyslog.conf.template"
MAAS_SYSLOG_WORK_DIR = "rsyslog"


class SyslogConfigFail(Exception):
    """Raised if there is a problem with the syslog configuration."""


def get_syslog_log_path():
    """Location of syslog log file outputs."""
    setting = os.getenv("MAAS_SYSLOG_LOG_DIR", "/var/log/maas")
    if isinstance(setting, bytes):
        fsenc = sys.getfilesystemencoding()
        setting = setting.decode(fsenc)
    return setting


def get_syslog_config_path():
    """Location of syslog configuration file."""
    setting = os.getenv("MAAS_SYSLOG_CONFIG_DIR", "/var/lib/maas")
    if isinstance(setting, bytes):
        fsenc = sys.getfilesystemencoding()
        setting = setting.decode(fsenc)
    setting = os.sep.join([setting, MAAS_SYSLOG_CONF_NAME])
    return setting


def get_syslog_workdir_path():
    """Location of syslog work directory."""
    setting = os.getenv("MAAS_SYSLOG_CONFIG_DIR", "/var/lib/maas")
    if isinstance(setting, bytes):
        fsenc = sys.getfilesystemencoding()
        setting = setting.decode(fsenc)
    setting = os.sep.join([setting, MAAS_SYSLOG_WORK_DIR])
    return setting


def is_config_present():
    """Check if there is a configuration file for the syslog server."""
    return os.access(get_syslog_config_path(), os.R_OK)


@synchronous
def write_config(write_local, forwarders=None, port=None, promtail_port=None):
    """Write the syslog configuration."""
    context = {
        "user": "maas",
        "group": "maas",
        "drop_priv": True,
        "work_dir": get_syslog_workdir_path(),
        "log_dir": get_syslog_log_path(),
        "write_local": write_local,
        "port": port if port else 5247,
        "forwarders": (
            sorted(forwarders, key=itemgetter("name"))
            if forwarders is not None
            else []
        ),
        "promtail_port": promtail_port if promtail_port else 0,
    }

    # Running inside the snap rsyslog is root.
    if snap.running_in_snap():
        context["user"] = "root"
        context["group"] = "root"
        context["drop_priv"] = False

    template_path = locate_template("syslog", MAAS_SYSLOG_CONF_TEMPLATE)
    template = tempita.Template.from_filename(template_path, encoding="UTF-8")
    try:
        content = template.substitute(context)
    except NameError as error:
        raise SyslogConfigFail(*error.args)  # noqa: B904

    # Squid prefers ascii.
    content = content.encode("ascii")
    target_path = get_syslog_config_path()
    atomic_write(content, target_path, overwrite=True, mode=0o644)
