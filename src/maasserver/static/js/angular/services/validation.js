/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Validation Service
 *
 * Used by controllers to validate user inputs.
 */

angular.module('MAAS').service('ValidationService', function() {

        // Pattern that matches a hostname.
        var hostnamePattern =
            /^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])*$/;

        // Pattern that matches a MAC.
        var macPattern = /^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$/;

        // Pattern used to match IPv4.
        var ipv4Pattern = new RegExp([
            '^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.',
            '(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.',
            '(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.',
            '(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
            ].join(''));

        // Returns true if the octets in one equal two with the cidr mask in
        // bits applied to both.
        function cidrMatcher(one, two, size, bits) {
            var part = 0;
            while(bits > 0) {
                var shift = size - bits;
                if(shift < 0) {
                    shift = 0;
                }

                var oneShift = one[part] >> shift;
                var twoShift = two[part] >> shift;
                if(oneShift !== twoShift) {
                    return false;
                }
                bits -= size;
                part += 1;
            }
            return true;
        }

        // Convert string ipv4 address into octets array.
        function ipv4ToOctets(ipAddress) {
            var parts = ipAddress.split('.');
            var octets = [];
            angular.forEach(parts, function(part) {
                octets.push(parseInt(part, 8));
            });
            return octets;
        }

        // Convert ipv6 address to a full ipv6 address, removing the
        // '::' shortcut.
        function ipv6Expand(ipAddress) {
            var i, expandedAddress = ipAddress;
            if(expandedAddress.indexOf("::") !== -1) {
                // '::' is present so replace it with the required
                // number of '0000:' based on its location in the string.
                var split = ipAddress.split("::");
                var groups = 0;
                for(i = 0; i < split.length; i++) {
                    groups += split[i].split(":").length;
                }
                expandedAddress = split[0] + ":";
                for(i = 0; i < 8 - groups; i++) {
                    expandedAddress += "0000:";
                }
                expandedAddress += split[1];
            }
            return expandedAddress;
        }

        // Convert string ipv6 into octets array.
        function ipv6ToOctets(ipAddress) {
            var octets = [];
            var parts = ipv6Expand(ipAddress).split(":");
            angular.forEach(parts, function(part) {
                octets.push(parseInt(part, 16));
            });
            return octets;
        }

        // Return true if the hostname is valid, false otherwise.
        this.validateHostname = function(hostname) {
            // Invalid if the hostname is not a string, empty, or more than
            // 63 characters.
            if(!angular.isString(hostname) ||
                hostname.length === 0 || hostname.length > 63) {
                return false;
            }
            return hostnamePattern.test(hostname);
        };

        // Return true if the MAC is valid, false otherwise.
        this.validateMAC = function(macAddress) {
            // Invalid if the macAddress is not a string.
            if(!angular.isString(macAddress)) {
                return false;
            }
            return macPattern.test(macAddress.trim());
        };

        // Return true if the IP is valid IPv4 address, false otherwise.
        this.validateIPv4 = function(ipAddress) {
            // Invalid if the ipAddress is not a string or empty.
            if(!angular.isString(ipAddress) || ipAddress.length === 0) {
                return false;
            }
            return ipv4Pattern.test(ipAddress);
        };

        // Return true if the IP is valid IPv6 address, false otherwise.
        this.validateIPv6 = function(ipAddress) {
            // Invalid if the ipAddress is not a string, empty, or missing
            // atleast one ':'.
            if(!angular.isString(ipAddress) ||
                ipAddress.length === 0 ||
                ipAddress.indexOf(':') === -1) {
                return false;
            }
            var expandedAddress = ipv6Expand(ipAddress);
            var octets = ipv6ToOctets(expandedAddress);
            if(octets.length !== 8) {
                return false;
            }

            // Make sure all octets are in range.
            var i;
            for(i = 0; i < 8; i++) {
                if(isNaN(octets[i]) || octets[i] < 0 || octets[i] > 0xffff) {
                    // Out of range.
                    return false;
                }
            }

            // Don't allow unspecified, loopback, multicast, link-local
            // unicast, or anything out of range.
            if(octets[0] < 1 ||
                octets[0] === 0xff00 ||
                octets[0] === 0xfe80) {
                return false;
            }
            return true;
        };

        // Return true if the IP is valid, false otherwise.
        this.validateIP = function(ipAddress) {
            return (
                this.validateIPv4(ipAddress) || this.validateIPv6(ipAddress));
        };

        // Return true if the ipAddress is in the network.
        this.validateIPInRange = function(ipAddress, network) {
            var networkSplit = network.split('/');
            var networkAddress = networkSplit[0];
            var cidrBits = parseInt(networkSplit[1], 10);

            if(this.validateIPv4(ipAddress) &&
                this.validateIPv4(networkAddress)) {
                return cidrMatcher(
                    ipv4ToOctets(ipAddress),
                    ipv4ToOctets(networkAddress),
                    8, cidrBits);
            } else if(this.validateIPv6(ipAddress) &&
                this.validateIPv6(networkAddress)) {
                return cidrMatcher(
                    ipv6ToOctets(ipAddress),
                    ipv6ToOctets(networkAddress),
                    16, cidrBits);
            }
            return false;
        };
    });
