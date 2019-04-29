/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Script results listing directive.
 *
 */

function maasScriptResultsList() {
  return {
    templateUrl:
      "static/partials/script-results-list.html?v=" + MAAS_config.files_version
  };
}

export default maasScriptResultsList;
