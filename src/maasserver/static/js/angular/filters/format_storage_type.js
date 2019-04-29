/* Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Converts storage type into human readable string, e.g. LVM
 */

function formatStorageType() {
  return function(storageType) {
    if (!storageType) {
      return "";
    }

    switch (storageType) {
      case "lvm":
        return "LVM";
      default:
        return storageType;
    }
  };
}

export default formatStorageType;
