/* Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Converts bytes into human readable string, e.g. 10 GB
 */

function formatBytes() {
  return function(bytes) {
      var bytesInKilobyte = 1000;
      var kilobytesInMegabyte = 1000;
      var megabytesInGigabyte = 1000;
      var gigabytesInTerabyte = 1000;

      var bytesInMegabyte = (
        bytesInKilobyte * kilobytesInMegabyte
      );
      var bytesInGigabyte = (
        bytesInKilobyte * kilobytesInMegabyte * megabytesInGigabyte
      );
      var bytesInTerabyte = (
        bytesInKilobyte *
        kilobytesInMegabyte *
        megabytesInGigabyte * gigabytesInTerabyte
      );

      if (bytes >= bytesInTerabyte) {
        return Math.round(
          bytes /
          bytesInKilobyte /
          kilobytesInMegabyte /
          megabytesInGigabyte /
          gigabytesInTerabyte
        ) + ' TB';
      } else if (bytes >= bytesInGigabyte) {
        return Math.round(
          bytes /
          bytesInKilobyte /
          kilobytesInMegabyte /
          megabytesInGigabyte
        ) +  ' GB';
      } else if (bytes >= bytesInMegabyte) {
        return Math.round(
          bytes /
          bytesInKilobyte /
          kilobytesInMegabyte
        ) + ' MB';
      } else if (bytes >= bytesInKilobyte) {
        return Math.round(bytes / bytesInKilobyte) + ' KB';
      } else if (bytes > 0) {
        return bytes + ' B';
      } else {
        return 0;
      }
  }
};

function convertGigabyteToBytes() {
  return function(gigabytes) {
      var bytesInKilobyte = 1000;
      var kilobytesInMegabyte = 1000;
      var megabytesInGigabyte = 1000;

      if (gigabytes) {
        return Math.round(
          gigabytes *
          bytesInKilobyte *
          kilobytesInMegabyte *
          megabytesInGigabyte
        );
      } else {
        return 0;
      }
  }
};

angular.module('MAAS').filter('formatBytes', formatBytes);
angular.module('MAAS').filter('convertGigabyteToBytes', convertGigabyteToBytes);
