/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Converter Service
 *
 * Used by controllers to convert user inputs.
 */

function ConverterService() {
  // Case is important: 1kB is 1000 bytes, whereas 1KB is 1024 bytes.
  // See https://en.wikipedia.org/wiki/Byte#Unit_symbol
  var UNITS = ["bytes", "kB", "MB", "GB", "TB"];

  var KILOBYTE = 1000.0;
  var MEGABYTE = 1000.0 * 1000.0;
  var GIGABYTE = 1000.0 * 1000.0 * 1000.0;
  var TERABYTE = 1000.0 * 1000.0 * 1000.0 * 1000.0;

  // Convert the bytes to a unit.
  this.bytesToUnits = function(bytes) {
    // Support string being passed.
    if (angular.isString(bytes)) {
      bytes = parseInt(bytes, 10);
    }

    var i,
      unit,
      converted = bytes;
    for (i = 0; i < UNITS.length; i++) {
      unit = UNITS[i];
      if (Math.abs(converted) < 1000.0 || unit === "TB") {
        var string = converted.toFixed(1) + " " + unit;
        if (unit === "bytes") {
          string = converted + " " + unit;
        }
        return {
          original: bytes,
          converted: converted,
          units: unit,
          string: string
        };
      }
      converted /= 1000.0;
    }
  };

  // Convert the data based on the unit to bytes.
  this.unitsToBytes = function(data, unit) {
    // Support string being passed.
    if (angular.isString(data)) {
      data = parseFloat(data);
    }
    if (unit === "bytes") {
      return Math.floor(data);
    } else if (unit === "kB") {
      return Math.floor(data * KILOBYTE);
    } else if (unit === "MB") {
      return Math.floor(data * MEGABYTE);
    } else if (unit === "GB") {
      return Math.floor(data * GIGABYTE);
    } else if (unit === "TB") {
      return Math.floor(data * TERABYTE);
    }
  };

  // Convert the data based on unit down to the lowest tolerance to still
  // be the same value in that unit.
  this.roundUnits = function(data, unit) {
    // Support string being passed.
    if (angular.isString(data)) {
      data = parseFloat(data);
    }
    if (unit === "bytes") {
      return Math.floor(data);
    } else if (unit === "kB") {
      return Math.floor(data * KILOBYTE) - 0.05 * KILOBYTE;
    } else if (unit === "MB") {
      return Math.floor(data * MEGABYTE) - 0.05 * MEGABYTE;
    } else if (unit === "GB") {
      return Math.floor(data * GIGABYTE) - 0.05 * GIGABYTE;
    } else if (unit === "TB") {
      return Math.floor(data * TERABYTE) - 0.05 * TERABYTE;
    }
  };

  // Round the bytes down to size based on the block size.
  this.roundByBlockSize = function(bytes, block_size) {
    return block_size * Math.floor(bytes / block_size);
  };

  // Convert string ipv4 address into octets array.
  this.ipv4ToOctets = function(ipAddress) {
    var parts = ipAddress.split(".");
    var octets = [];
    angular.forEach(parts, function(part) {
      octets.push(parseInt(part, 10));
    });
    return octets;
  };

  // Convert string ipv4 address into integer.
  this.ipv4ToInteger = function(ipAddress) {
    var octets = this.ipv4ToOctets(ipAddress);
    return (
      octets[0] * Math.pow(256, 3) +
      octets[1] * Math.pow(256, 2) +
      octets[2] * 256 +
      octets[3]
    );
  };

  // Convert ipv6 address to a full ipv6 address, removing the
  // '::' shortcut and padding each group with zeros.
  this.ipv6Expand = function(ipAddress) {
    var i,
      expandedAddress = ipAddress;
    if (expandedAddress.indexOf("::") !== -1) {
      // '::' is present so replace it with the required
      // number of '0000:' based on its location in the string.
      var split = ipAddress.split("::");
      var groups = 0;
      for (i = 0; i < split.length; i++) {
        groups += split[i].split(":").length;
      }
      expandedAddress = split[0] + ":";
      for (i = 0; i < 8 - groups; i++) {
        expandedAddress += "0000:";
      }
      expandedAddress += split[1];
    }
    // Pad the output of each part with zeros.
    var output = [],
      parts = expandedAddress.split(":");
    angular.forEach(parts, function(part) {
      output.push("0000".substr(part.length) + part);
    });
    return output.join(":");
  };

  // Convert string ipv6 into groups array.
  this.ipv6ToGroups = function(ipAddress) {
    var groups = [];
    var parts = this.ipv6Expand(ipAddress).split(":");
    angular.forEach(parts, function(part) {
      groups.push(parseInt(part, 16));
    });
    return groups;
  };
}

export default ConverterService;
