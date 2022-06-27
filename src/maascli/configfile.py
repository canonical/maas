"""Read/write maas config files."""

import os
from pathlib import Path

import yaml


class MAASConfiguration:
    """Manager class for MAAS configuration files."""

    DEFAULT_CONFIG_DIR = "/etc/maas"

    def __init__(self, environ=None):
        if environ is None:
            environ = os.environ
        self._environ = environ

    def get(self):
        """Return a dict with the current configuration."""
        return self._get_from_file("regiond.conf")

    def update(self, configs):
        """Add or update specified configuration entries."""
        rackd_config = {}
        self._update_file(configs, "regiond.conf")
        if "maas_url" in configs:
            rackd_config["maas_url"] = configs["maas_url"]
        if "debug" in configs:
            rackd_config["debug"] = configs["debug"]
        if rackd_config:
            self._update_file(rackd_config, "rackd.conf")

    def write_to_file(self, data, filename):
        """Write the configuration data to `regiond.conf`."""
        config_file = self._config_dir / filename
        config_file.write_text(yaml.safe_dump(data, default_flow_style=False))

    @property
    def _config_dir(self):
        return Path(self._environ.get("SNAP_DATA", self.DEFAULT_CONFIG_DIR))

    def _get_from_file(self, filename):
        """Return a dict with the config from the specified file."""
        config_file = self._config_dir / filename
        if not config_file.exists():
            return {}
        data = yaml.safe_load(config_file.read_text())
        # if the file exists but is empty, data can be None
        return data or {}

    def _update_file(self, configs, filename):
        """Update configuration for the specified file."""
        data = self._get_from_file(filename)
        data.update(configs)
        # remove empty keys
        data = {key: value for key, value in data.items() if value is not None}
        self.write_to_file(data, filename)
