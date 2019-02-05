# Copyright 2019 Canonical Ltd.  This software is licensed under the
# GNU Affero General Public License version 3 (see the file LICENSE).

try:
    import prometheus_client as prom_cli
except ImportError:
    prom_cli = None


# whether Prometheus support is available
PROMETHEUS_SUPPORTED = prom_cli is not None
