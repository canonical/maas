#!/usr/bin/env python3
#
# maas-run-remote-scripts - Download a set of scripts from the MAAS region,
#                           execute them, and send the results back.
#
# Author: Lee Trager <lee.trager@canonical.com>
#
# Copyright (C) 2017 Canonical
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import copy
from datetime import timedelta
from io import BytesIO
import json
import os
import re
import shlex
from subprocess import (
    check_output,
    DEVNULL,
    PIPE,
    Popen,
    TimeoutExpired,
)
import sys
import tarfile
from threading import (
    Event,
    Thread,
)
import time
import zipfile


try:
    from maas_api_helper import (
        geturl,
        MD_VERSION,
        read_config,
        signal,
        SignalException,
        capture_script_output,
    )
except ImportError:
    # For running unit tests.
    from snippets.maas_api_helper import (
        geturl,
        MD_VERSION,
        read_config,
        signal,
        SignalException,
        capture_script_output,
    )


def fail(msg):
    sys.stderr.write("FAIL: %s" % msg)
    sys.exit(1)


def signal_wrapper(*args, **kwargs):
    """Wrapper to output any SignalExceptions to STDERR."""
    try:
        signal(*args, **kwargs)
    except SignalException as e:
        fail(e.error)


def download_and_extract_tar(url, creds, scripts_dir):
    """Download and extract a tar from the given URL.

    The URL may contain a compressed or uncompressed tar.
    """
    binary = BytesIO(geturl(url, creds))

    with tarfile.open(mode='r|*', fileobj=binary) as tar:
        tar.extractall(scripts_dir)


def run_and_check(
        cmd, combined_path, stdout_path, stderr_path, script_name, args,
        ignore_error=False):
    proc = Popen(cmd, stdin=DEVNULL, stdout=PIPE, stderr=PIPE)
    capture_script_output(proc, combined_path, stdout_path, stderr_path)
    if proc.returncode != 0 and not ignore_error:
        args['exit_status'] = proc.returncode
        args['files'] = {
            script_name: open(combined_path, 'rb').read(),
            '%s.out' % script_name: open(stdout_path, 'rb').read(),
            '%s.err' % script_name: open(stderr_path, 'rb').read(),
        }
        signal_wrapper(
            error='Failed installing package(s) for %s' % (
                script_name), **args)
        return False
    else:
        return True


def install_dependencies(
        args, script, combined_path, stdout_path, stderr_path, download_path):
    """Download and install any required packaged for the script to run."""
    args = copy.deepcopy(args)
    args['status'] = 'INSTALLING'
    packages = script.get('packages', {})
    apt = packages.get('apt')
    snap = packages.get('snap')
    url = packages.get('url')

    if apt is not None:
        signal_wrapper(
            error='Installing apt packages for %s' % script['name'], **args)
        if not run_and_check(
                ['sudo', '-n', 'apt-get', '-qy', 'install'] + apt,
                combined_path, stdout_path, stderr_path, script['name'], args):
            return False

    if snap is not None:
        signal_wrapper(
            error='Installing snap packages for %s' % script['name'], **args)
        for pkg in snap:
            if isinstance(pkg, str):
                cmd = ['sudo', '-n', 'snap', 'install', pkg]
            elif isinstance(pkg, dict):
                cmd = ['sudo', '-n', 'snap', 'install', pkg['name']]
                if 'channel' in pkg:
                    cmd.append('--%s' % pkg['channel'])
                if 'mode' in pkg:
                    if pkg['mode'] == 'classic':
                        cmd.append('--classic')
                    else:
                        cmd.append('--%smode' % pkg['mode'])
            else:
                # The ScriptForm validates that each snap package should be a
                # string or dictionary. This should never happen but just
                # incase it does...
                continue
            if not run_and_check(
                    cmd, combined_path, stdout_path, stderr_path,
                    script['name'], args):
                return False

    if url is not None:
        signal_wrapper(
            error='Downloading and extracting URLs for %s' % script['name'],
            **args)
        path_regex = re.compile("^Saving to: ['‘](?P<path>.+)['’]$", re.M)
        os.makedirs(download_path, exist_ok=True)
        for i in url:
            # wget supports multiple protocols, proxying, proper error message,
            # handling user input without protocol information, and getting the
            # filename from the request. Shell out and capture its output
            # instead of implementing all of that here.
            if not run_and_check(
                    ['wget', i, '-P', download_path], combined_path,
                    stdout_path, stderr_path, script['name'], args):
                return False

            # Get the filename from the captured output incase the URL does not
            # include a filename. e.g the URL 'ubuntu.com' will create an
            # index.html file.
            with open(combined_path, 'r') as combined:
                m = path_regex.findall(combined.read())
                if m != []:
                    filename = m[-1]
                else:
                    # Unable to find filename in output.
                    continue

            if tarfile.is_tarfile(filename):
                with tarfile.open(filename, 'r|*') as tar:
                    tar.extractall(download_path)
            elif zipfile.is_zipfile(filename):
                with zipfile.ZipFile(filename, 'r') as z:
                    z.extractall(download_path)
            elif filename.endswith('.deb'):
                # Allow dpkg to fail incase it just needs dependencies
                # installed.
                run_and_check(
                    ['sudo', '-n', 'dpkg', '-i', filename],
                    combined_path, stdout_path, stderr_path, script['name'],
                    args, True)
                if not run_and_check(
                        ['sudo', '-n', 'apt-get', 'install', '-qyf'],
                        combined_path, stdout_path, stderr_path,
                        script['name'], args):
                    return False
            elif filename.endswith('.snap'):
                if not run_and_check(
                        ['sudo', '-n', 'snap', filename],
                        combined_path, stdout_path, stderr_path,
                        script['name'], args):
                    return False

    # All went well, clean up the install logs so only script output is
    # captured.
    for path in [combined_path, stdout_path, stderr_path]:
        if os.path.exists(path):
            os.remove(path)

    return True


# Cache the block devices so we only have to query once.
_block_devices = None


def get_block_devices():
    """If needed, query lsblk for all known block devices and store."""
    global _block_devices
    if _block_devices is None:
        _block_devices = []
        block_list = check_output([
            'lsblk', '--exclude', '1,2,7', '-d', '-P', '-o',
            'NAME,MODEL,SERIAL']).decode('utf-8')
        for blockdev in block_list.splitlines():
            tokens = shlex.split(blockdev)
            current_block = {}
            for token in tokens:
                k, v = token.split("=", 1)
                current_block[k] = v.strip()
            _block_devices.append(current_block)

    return _block_devices


def parse_parameters(script, scripts_dir):
    """Return a list containg script path and parameters to be passed to it."""
    ret = [os.path.join(scripts_dir, script['path'])]
    for param in script.get('parameters', {}).values():
        param_type = param.get('type')
        if param_type == 'runtime':
            argument_format = param.get('argument_format', '--runtime={input}')
            ret += argument_format.format(input=param['value']).split()
        elif param_type == 'storage':
            value = param['value']
            if not (value.get('model') and value.get('serial')):
                # If no model or serial were included trust that id_path
                # is correct. This is needed for VirtIO devices.
                value['path'] = value['input'] = value['id_path']
            else:
                # Map the current path of the device to what it currently is
                # for the device model and serial. This is needed as the
                # the device name may have changed since commissioning.
                for blockdev in get_block_devices():
                    if (value['model'] == blockdev['MODEL'] and
                            value['serial'] == blockdev['SERIAL']):
                        value['path'] = value['input'] = "/dev/%s" % blockdev[
                            'NAME']
            argument_format = param.get(
                'argument_format', '--storage={path}')
            ret += argument_format.format(**value).split()
    return ret


def run_scripts(url, creds, scripts_dir, out_dir, scripts):
    """Run and report results for the given scripts."""
    total_scripts = len(scripts)
    fail_count = 0
    base_args = {
        'url': url,
        'creds': creds,
        'status': 'WORKING',
    }
    for i, script in enumerate(scripts):
        i += 1
        args = copy.deepcopy(base_args)
        args['script_result_id'] = script['script_result_id']
        script_version_id = script.get('script_version_id')
        if script_version_id is not None:
            args['script_version_id'] = script_version_id
        timeout_seconds = script.get('timeout_seconds')
        for param in script.get('parameters', {}).values():
            if param.get('type') == 'runtime':
                timeout_seconds = param['value']
                break

        # Create a seperate output directory for each script being run as
        # multiple scripts with the same name may be run.
        script_out_dir = os.path.join(out_dir, '%s.%s' % (
            script['name'], script['script_result_id']))
        os.makedirs(script_out_dir, exist_ok=True)
        combined_path = os.path.join(script_out_dir, script['name'])
        stdout_name = '%s.out' % script['name']
        stdout_path = os.path.join(script_out_dir, stdout_name)
        stderr_name = '%s.err' % script['name']
        stderr_path = os.path.join(script_out_dir, stderr_name)
        result_name = '%s.yaml' % script['name']
        result_path = os.path.join(script_out_dir, result_name)
        download_path = os.path.join(scripts_dir, 'downloads', script['name'])

        if not install_dependencies(
                args, script, combined_path, stdout_path, stderr_path,
                download_path):
            fail_count += 1
            continue

        signal_wrapper(
            error='Starting %s [%d/%d]' % (
                script['name'], i, len(scripts)),
            **args)

        env = copy.deepcopy(os.environ)
        env['OUTPUT_COMBINED_PATH'] = combined_path
        env['OUTPUT_STDOUT_PATH'] = stdout_path
        env['OUTPUT_STDERR_PATH'] = stderr_path
        env['RESULT_PATH'] = result_path
        env['DOWNLOAD_PATH'] = download_path

        try:
            script_arguments = parse_parameters(script, scripts_dir)
        except KeyError:
            # 2 is the return code bash gives when it can't execute.
            args['exit_status'] = 2
            args['files'] = {
                script['name']: b'Unable to map parameters',
                stderr_name: b'Unable to map parameters',
            }
            signal_wrapper(
                error='Failed to execute %s [%d/%d]: %d' % (
                    script['name'], i, total_scripts, args['exit_status']),
                **args)
            continue

        try:
            # This script sets its own niceness value to the highest(-20) below
            # to help ensure the heartbeat keeps running. When launching the
            # script we need to lower the nice value as a child process
            # inherits the parent processes niceness value. preexec_fn is
            # executed in the child process before the command is run. When
            # setting the nice value the kernel adds the current nice value
            # to the provided value. Since the runner uses a nice value of -20
            # setting it to 40 gives the actual nice value of 20.
            proc = Popen(
                script_arguments, stdout=PIPE, stderr=PIPE, env=env,
                preexec_fn=lambda: os.nice(40))
            capture_script_output(
                proc, combined_path, stdout_path, stderr_path, timeout_seconds)
        except OSError as e:
            fail_count += 1
            if isinstance(e.errno, int) and e.errno != 0:
                args['exit_status'] = e.errno
            else:
                # 2 is the return code bash gives when it can't execute.
                args['exit_status'] = 2
            result = str(e).encode()
            if result == b'':
                result = b'Unable to execute script'
            args['files'] = {
                script['name']: result,
                stderr_name: result,
            }
            signal_wrapper(
                error='Failed to execute %s [%d/%d]: %d' % (
                    script['name'], i, total_scripts, args['exit_status']),
                **args)
        except TimeoutExpired:
            fail_count += 1
            args['status'] = 'TIMEDOUT'
            args['files'] = {
                script['name']: open(combined_path, 'rb').read(),
                stdout_name: open(stdout_path, 'rb').read(),
                stderr_name: open(stderr_path, 'rb').read(),
            }
            if os.path.exists(result_path):
                args['files'][result_name] = open(result_path, 'rb').read()
            signal_wrapper(
                error='Timeout(%s) expired on %s [%d/%d]' % (
                    str(timedelta(seconds=timeout_seconds)), script['name'], i,
                    total_scripts),
                **args)
        else:
            if proc.returncode != 0:
                fail_count += 1
            args['exit_status'] = proc.returncode
            args['files'] = {
                script['name']: open(combined_path, 'rb').read(),
                stdout_name: open(stdout_path, 'rb').read(),
                stderr_name: open(stderr_path, 'rb').read(),
            }
            if os.path.exists(result_path):
                args['files'][result_name] = open(result_path, 'rb').read()
            signal_wrapper(
                error='Finished %s [%d/%d]: %d' % (
                    script['name'], i, len(scripts), args['exit_status']),
                **args)

    # Signal failure after running commissioning or testing scripts so MAAS
    # transisitions the node into FAILED_COMMISSIONING or FAILED_TESTING.
    if fail_count != 0:
        signal_wrapper(
            url, creds, 'FAILED', '%d scripts failed to run' % fail_count)

    return fail_count


def run_scripts_from_metadata(url, creds, scripts_dir, out_dir):
    """Run all scripts from a tar given by MAAS."""
    with open(os.path.join(scripts_dir, 'index.json')) as f:
        scripts = json.load(f)['1.0']

    fail_count = 0
    commissioning_scripts = scripts.get('commissioning_scripts')
    if commissioning_scripts is not None:
        fail_count += run_scripts(
            url, creds, scripts_dir, out_dir, commissioning_scripts)
        if fail_count != 0:
            return

    testing_scripts = scripts.get('testing_scripts')
    if testing_scripts is not None:
        # If the node status was COMMISSIONING transition the node into TESTING
        # status. If the node is already in TESTING status this is ignored.
        signal_wrapper(url, creds, 'TESTING')

        # If commissioning previously ran and a test script uses a storage
        # parameter redownload the script tar as the storage devices may have
        # changed causing different ScriptResults.
        if commissioning_scripts is not None:
            for test_script in testing_scripts:
                for param in test_script.get('parameters', {}).values():
                    if param['type'] == 'storage':
                        download_and_extract_tar(
                            "%s/maas-scripts/" % url, creds, scripts_dir)
                        return run_scripts_from_metadata(
                            url, creds, scripts_dir, out_dir)

        fail_count += run_scripts(
            url, creds, scripts_dir, out_dir, testing_scripts)

    # Only signal OK when we're done with everything and nothing has failed.
    if fail_count == 0:
        signal_wrapper(url, creds, 'OK', 'All scripts successfully ran')


class HeartBeat(Thread):
    """Creates a background thread which pings the MAAS metadata service every
    two minutes to let it know we're still up and running scripts. If MAAS
    doesn't hear from us it will assume something has gone wrong and power off
    the node.
    """

    def __init__(self, url, creds):
        super().__init__(name='HeartBeat')
        self._url = url
        self._creds = creds
        self._run = Event()
        self._run.set()

    def stop(self):
        self._run.clear()

    def run(self):
        # Record the relative start time of the entire run.
        start = time.monotonic()
        tenths = 0
        while self._run.is_set():
            # Record the start of this heartbeat interval.
            heartbeat_start = time.monotonic()
            heartbeat_elapsed = 0
            total_elapsed = heartbeat_start - start
            args = [self._url, self._creds, 'WORKING']
            # Log the elapsed time plus the measured clock skew, if this
            # is the second run through the loop.
            if tenths > 0:
                args.append(
                    'Elapsed time (real): %d.%ds; Python: %d.%ds' % (
                        total_elapsed, total_elapsed % 1 * 10,
                        tenths // 10, tenths % 10))
            signal_wrapper(*args)
            # Spin for 2 minutes before sending another heartbeat.
            while heartbeat_elapsed < 120 and self._run.is_set():
                heartbeat_end = time.monotonic()
                heartbeat_elapsed = heartbeat_end - heartbeat_start
                # Wake up every tenth of a second to record clock skew and
                # ensure delayed scheduling doesn't impact the heartbeat.
                time.sleep(0.1)
                tenths += 1


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description='Download and run scripts from the MAAS metadata service.')
    parser.add_argument(
        "--config", metavar="file", help="Specify config file", default=None)
    parser.add_argument(
        "--ckey", metavar="key", help="The consumer key to auth with",
        default=None)
    parser.add_argument(
        "--tkey", metavar="key", help="The token key to auth with",
        default=None)
    parser.add_argument(
        "--csec", metavar="secret", help="The consumer secret (likely '')",
        default="")
    parser.add_argument(
        "--tsec", metavar="secret", help="The token secret to auth with",
        default=None)
    parser.add_argument(
        "--apiver", metavar="version",
        help="The apiver to use (\"\" can be used)", default=MD_VERSION)
    parser.add_argument(
        "--url", metavar="url", help="The data source to query", default=None)

    parser.add_argument(
        "storage_directory",
        help="Directory to store the extracted data from the metadata service."
    )

    args = parser.parse_args()

    creds = {
        'consumer_key': args.ckey,
        'token_key': args.tkey,
        'token_secret': args.tsec,
        'consumer_secret': args.csec,
        'metadata_url': args.url,
        }

    if args.config:
        read_config(args.config, creds)

    url = creds.get('metadata_url')
    if url is None:
        fail("URL must be provided either in --url or in config\n")
    url = "%s/%s/" % (url, args.apiver)

    # Disable the OOM killer on the runner process, the OOM killer will still
    # go after any tests spawned.
    oom_score_adj_path = os.path.join(
        '/proc', str(os.getpid()), 'oom_score_adj')
    open(oom_score_adj_path, 'w').write('-1000')
    # Give the runner the highest nice value to ensure the heartbeat keeps
    # running.
    os.nice(-20)

    heart_beat = HeartBeat(url, creds)
    heart_beat.start()

    scripts_dir = os.path.join(args.storage_directory, 'scripts')
    os.makedirs(scripts_dir)
    out_dir = os.path.join(args.storage_directory, 'out')
    os.makedirs(out_dir)

    download_and_extract_tar("%s/maas-scripts/" % url, creds, scripts_dir)
    run_scripts_from_metadata(url, creds, scripts_dir, out_dir)

    heart_beat.stop()


if __name__ == '__main__':
    main()
