/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS JSON Service
 *
 * Used by controllers to parse JSON.
 */

function JSONService() {
  // Return the JSON for the string or null if it cannot be parsed.
  this.tryParse = function(jsonString) {
    try {
      var obj = JSON.parse(jsonString);
      // JSON.parse(false) or JSON.parse(1234) will throw errors, but
      // JSON.parse(null) returns 'null', and typeof null === "object".
      if (obj && typeof obj === "object" && obj !== null) {
        return obj;
      }
    } catch (e) {
      // Ignore this error.
    }
    return null;
  };
}

export default JSONService;
