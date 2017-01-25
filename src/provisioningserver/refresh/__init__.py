# Copyright 2016-2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

"""Functionality to refresh rack controller hardware and networking details."""
import os
import socket
import stat
import subprocess
import tempfile

from provisioningserver.logger import get_maas_logger
from provisioningserver.refresh.maas_api_helper import (
    MD_VERSION,
    signal,
    SignalException,
)
from provisioningserver.refresh.node_info_scripts import NODE_INFO_SCRIPTS
from provisioningserver.utils.network import get_all_interfaces_definition
from provisioningserver.utils.shell import (
    call_and_check,
    ExternalProcessError,
)
from provisioningserver.utils.twisted import synchronous


maaslog = get_maas_logger("refresh")


def get_architecture():
    """Get the architecture of the running system."""
    try:
        stdout = call_and_check('archdetect').decode('utf-8')
    except ExternalProcessError:
        return ''
    arch, subarch = stdout.strip().split('/')
    if arch in ['i386', 'amd64', 'arm64', 'ppc64el']:
        subarch = 'generic'
    return '%s/%s' % (arch, subarch)


def get_os_release():
    """Parse the contents of /etc/os-release into a dictionary."""
    def full_strip(value):
        return value.strip().strip('\'"')

    os_release = {}
    with open('/etc/os-release') as f:
        for line in f:
            key, value = line.split('=')
            os_release[full_strip(key)] = full_strip(value)

    return os_release


@synchronous
def get_sys_info():
    """Return basic system information in a dictionary."""
    os_release = get_os_release()
    if 'ID' in os_release:
        osystem = os_release['ID']
    elif 'NAME' in os_release:
        osystem = os_release['NAME']
    else:
        osystem = ''
    if 'UBUNTU_CODENAME' in os_release:
        distro_series = os_release['UBUNTU_CODENAME']
    elif 'VERSION_ID' in os_release:
        distro_series = os_release['VERSION_ID']
    else:
        distro_series = ''
    return {
        'hostname': socket.gethostname().split('.')[0],
        'architecture': get_architecture(),
        'osystem': osystem,
        'distro_series': distro_series,
        'interfaces': get_all_interfaces_definition(),
    }


def signal_wrapper(*args, **kwargs):
    """Wrapper to capture and log any SignalException from signal."""
    try:
        signal(*args, **kwargs)
    except SignalException as e:
        maaslog.error("Error during controller refresh: %s" % e.error)


@synchronous
def refresh(system_id, consumer_key, token_key, token_secret, maas_url=None):
    """Run all builtin commissioning scripts and report results to region."""
    maaslog.info(
        "Refreshing rack controller hardware information.")

    if maas_url is None:
        maas_url = 'http://127.0.0.1:5240/MAAS'
    url = "%s/metadata/%s/" % (maas_url, MD_VERSION)

    creds = {
        'consumer_key': consumer_key,
        'token_key': token_key,
        'token_secret': token_secret,
        'consumer_secret': '',
    }

    scripts = {
        name: config
        for name, config in NODE_INFO_SCRIPTS.items()
        if config['run_on_controller']
    }

    with tempfile.TemporaryDirectory(prefix='maas-commission-') as tmpdir:
        failed_scripts = runscripts(scripts, url, creds, tmpdir=tmpdir)

    if len(failed_scripts) == 0:
        signal_wrapper(
            url, creds, 'OK', 'Finished refreshing %s' % system_id)
    else:
        signal_wrapper(
            url, creds, 'FAILED', 'Failed refreshing %s' % system_id)


def runscripts(scripts, url, creds, tmpdir):
    total_scripts = len(scripts)
    current_script = 1
    failed_scripts = []
    for script_name, builtin_script in scripts.items():
        signal_wrapper(
            url, creds, 'WORKING', 'Starting %s [%d/%d]' %
            (script_name, current_script, total_scripts))

        # Write script to /tmp and set it executable
        script_path = os.path.join(tmpdir, script_name)
        with open(script_path, 'wb') as f:
            f.write(builtin_script['content'])
        st = os.stat(script_path)
        os.chmod(script_path, st.st_mode | stat.S_IEXEC)

        # Execute script and store stdout/stderr
        proc = subprocess.Popen(
            script_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = proc.communicate()
        signal_wrapper(
            url, creds,
            "WORKING", "Finished %s [%d/%d]: %d" %
            (script_name, current_script, total_scripts, proc.returncode),
            files={script_name: stdout, "%s.err" % script_name: stderr},
            exit_status=proc.returncode)
        if proc.returncode != 0:
            failed_scripts.append(script_name)
        current_script += 1
    return failed_scripts
