# Copyright 2017 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

import os
import subprocess

import snapcraft


class BZRVersionPlugin(snapcraft.BasePlugin):
    """Plugin that patches snapcraft to append the version of the branch
    to the version string in the snapcraft.yaml."""

    def __init__(self, *args, **kwargs):
        super(BZRVersionPlugin, self).__init__(*args, **kwargs)
        # Patch snapcraft so the bzr revno is attached to the version
        # of the snap. This really should be built inside of snapcraft.
        create_packaging = snapcraft.internal.meta.create_snap_packaging

        def wrap_create_packaging(config_data, project_options):
            try:
                revno = subprocess.check_output([
                    'bzr', 'revno',
                    os.path.abspath(os.path.dirname(self.project.parts_dir))])
            except subprocess.CalledProcessError:
                # This can fail when using 'cleanbuild'. This is because the
                # bazaar branch can depend on a parent that is not copied into
                # the container.
                revno = b'UNKNOWN'
            config_data['version'] += (
                '+bzr%s-snap' % revno.decode('utf-8').strip())
            return create_packaging(config_data, project_options)

        snapcraft.internal.meta.create_snap_packaging = wrap_create_packaging
