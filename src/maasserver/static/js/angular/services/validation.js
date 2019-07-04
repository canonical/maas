/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Validation Service
 *
 * Used by controllers to validate user inputs.
 */

/* @ngInject */
function ValidationService(ConverterService) {
  // Pattern that matches a domainname.
  // XXX 2016-02-24 lamont: This also matches "example.com.",
  // which is wrong.
  var domainnamePattern = /^([a-z\d]|[a-z\d][a-z\d-.]*[a-z\d])*$/i;

  // Pattern that matches a hostname.
  var hostnamePattern = /^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9])*$/;

  // Pattern that matches a MAC.
  var macPattern = /^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$/;

  // Pattern used to match IPv4.
  var ipv4Pattern = new RegExp(
    [
      "^(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.",
      "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.",
      "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\\.",
      "(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$"
    ].join("")
  );

  // Returns true if the octets in one equal two with the cidr mask in
  // bits applied to both.
  function cidrMatcher(one, two, size, bits) {
    var part = 0;
    while (bits > 0) {
      var shift = size - bits;
      if (shift < 0) {
        shift = 0;
      }

      var oneShift = one[part] >> shift;
      var twoShift = two[part] >> shift;
      if (oneShift !== twoShift) {
        return false;
      }
      bits -= size;
      part += 1;
    }
    return true;
  }

  // Return true if the domainname is valid, false otherwise.
  this.validateDomainName = function(domainname) {
    // Invalid if the domain is not a string, empty, or more than
    // 253 characters.
    if (
      !angular.isString(domainname) ||
      domainname.length === 0 ||
      domainname.length > 253
    ) {
      return false;
    }
    return domainnamePattern.test(domainname);
  };

  // Return true if the hostname is valid, false otherwise.
  this.validateHostname = function(hostname) {
    // Invalid if the hostname is not a string, empty, or more than
    // 63 characters.
    if (
      !angular.isString(hostname) ||
      hostname.length === 0 ||
      hostname.length > 63
    ) {
      return false;
    }
    return hostnamePattern.test(hostname);
  };

  // Return true if the MAC is valid, false otherwise.
  this.validateMAC = function(macAddress) {
    // Invalid if the macAddress is not a string.
    if (!angular.isString(macAddress)) {
      return false;
    }
    return macPattern.test(macAddress.trim());
  };

  // Return true if the IP is valid IPv4 address, false otherwise.
  this.validateIPv4 = function(ipAddress) {
    // Invalid if the ipAddress is not a string or empty.
    if (!angular.isString(ipAddress) || ipAddress.length === 0) {
      return false;
    }
    return ipv4Pattern.test(ipAddress);
  };

  // Return true if the IP is valid IPv6 address, false otherwise.
  this.validateIPv6 = function(ipAddress) {
    // Invalid if the ipAddress is not a string, empty, or missing
    // at least one ':'.
    if (
      !angular.isString(ipAddress) ||
      ipAddress.length === 0 ||
      ipAddress.indexOf(":") === -1
    ) {
      return false;
    }
    var expandedAddress = ConverterService.ipv6Expand(ipAddress);
    var octets = ConverterService.ipv6ToGroups(expandedAddress);
    if (octets.length !== 8) {
      return false;
    }

    // Make sure all octets are in range.
    var i;
    for (i = 0; i < 8; i++) {
      if (isNaN(octets[i]) || octets[i] < 0 || octets[i] > 0xffff) {
        // Out of range.
        return false;
      }
    }

    // Don't allow unspecified, loopback, multicast, link-local
    // unicast, or anything out of range.
    if (octets[0] < 1 || octets[0] === 0xff00 || octets[0] === 0xfe80) {
      return false;
    }
    return true;
  };

  // Return true if the IP is valid, false otherwise.
  this.validateIP = function(ipAddress) {
    return this.validateIPv4(ipAddress) || this.validateIPv6(ipAddress);
  };

  // Return true if the ipAddress is in the network.
  this.validateIPInNetwork = function(ipAddress, network) {
    var networkSplit = network.split("/");
    var networkAddress = networkSplit[0];
    var cidrBits = parseInt(networkSplit[1], 10);

    if (this.validateIPv4(ipAddress) && this.validateIPv4(networkAddress)) {
      return cidrMatcher(
        ConverterService.ipv4ToOctets(ipAddress),
        ConverterService.ipv4ToOctets(networkAddress),
        8,
        cidrBits
      );
    } else if (
      this.validateIPv6(ipAddress) &&
      this.validateIPv6(networkAddress)
    ) {
      return cidrMatcher(
        ConverterService.ipv6ToGroups(ipAddress),
        ConverterService.ipv6ToGroups(networkAddress),
        16,
        cidrBits
      );
    }
    return false;
  };

  // Return true if the ipAddress is in the network and between the
  // lowAddress and highAddress inclusive.
  this.validateIPInRange = function(
    ipAddress,
    network,
    lowAddress,
    highAddress
  ) {
    // If the ip address is not even in the network then its
    // not in the range.
    if (!this.validateIPInNetwork(ipAddress, network)) {
      return false;
    }

    var i, ipOctets, lowOctets, highOctets;
    if (
      this.validateIPv4(ipAddress) &&
      this.validateIPv4(lowAddress) &&
      this.validateIPv4(highAddress)
    ) {
      // Check that each octet is of the ip address is more or equal
      // to the low address and less or equal to the high address.
      ipOctets = ConverterService.ipv4ToOctets(ipAddress);
      lowOctets = ConverterService.ipv4ToOctets(lowAddress);
      highOctets = ConverterService.ipv4ToOctets(highAddress);
      for (i = 0; i < 4; i++) {
        if (ipOctets[i] > highOctets[i] || ipOctets[i] < lowOctets[i]) {
          return false;
        }
      }
      return true;
    } else if (
      this.validateIPv6(ipAddress) &&
      this.validateIPv6(lowAddress) &&
      this.validateIPv6(highAddress)
    ) {
      // Check that each octet is of the ip address is more or equal
      // to the low address and less or equal to the high address.
      ipOctets = ConverterService.ipv6ToGroups(ipAddress);
      lowOctets = ConverterService.ipv6ToGroups(lowAddress);
      highOctets = ConverterService.ipv6ToGroups(highAddress);
      for (i = 0; i < 8; i++) {
        if (ipOctets[i] > highOctets[i] || ipOctets[i] < lowOctets[i]) {
          return false;
        }
      }
      return true;
    }
    return false;
  };
}

export default ValidationService;
