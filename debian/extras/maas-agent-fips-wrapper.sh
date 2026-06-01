#!/bin/sh
# Copyright (c) 2026 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Wrapper script to activate Go FIPS mode for maas-agent when
# the host is running in FIPS mode. This must be called before
# maas-agent starts to ensure crypto operations use FIPS-compliant
# algorithms.

# Check if FIPS mode is enabled on the host
if [ -r /proc/sys/crypto/fips_enabled ] && [ "$(cat /proc/sys/crypto/fips_enabled 2>/dev/null)" = "1" ]; then
    export GODEBUG=fips140=on
fi

exec /usr/sbin/maas-agent "$@"
