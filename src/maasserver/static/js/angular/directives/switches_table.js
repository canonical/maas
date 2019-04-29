/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Switches listing directive.
 *
 * Renders the switches listing.
 */

/* @ngInject */
function maasSwitchesTable(SwitchesManager, GeneralManager) {
  return {
    restrict: "E",
    scope: {
      search: "=",
      ngDisabled: "&",
      switchHasError: "&",
      hideCheckboxes: "=?",
      onListingChange: "&",
      onCheckAll: "&",
      onCheck: "&"
    },
    templateUrl:
      "static/partials/switches-table.html?v=" + MAAS_config.files_version,
    link: function(scope, element, attrs) {
      // Statuses that should show spinner.
      var SPINNER_STATUSES = [
        1, // commissioning
        9, // deploying
        12, // releasing
        14, // disk erasing
        17, // entering rescue mode
        19, // exiting rescue mode
        21 // testing
      ];

      // Scope variables.
      scope.table = {
        column: "fqdn",
        predicate: "fqdn",
        reverse: false,
        allViewableChecked: false,
        switches: SwitchesManager.getItems(),
        filteredSwitches: [],
        osinfo: GeneralManager.getData("osinfo")
      };

      // Ensures that the checkbox for select all is the correct value.
      scope.updateAllChecked = function() {
        // Not checked when the filtered switches are empty.
        if (scope.table.filteredSwitches.length === 0) {
          scope.table.allViewableChecked = false;
          return;
        }

        // Loop through all filtered switches and see if all are checked.
        var i;
        for (i = 0; i < scope.table.filteredSwitches.length; i++) {
          if (!scope.table.filteredSwitches[i].$selected) {
            scope.table.allViewableChecked = false;
            return;
          }
        }
        scope.table.allViewableChecked = true;
      };

      // Selects and deselects visible switches.
      scope.toggleCheckAll = function() {
        if (scope.table.allViewableChecked) {
          angular.forEach(scope.table.filteredSwitches, function(switch_) {
            SwitchesManager.unselectItem(switch_.system_id);
          });
        } else {
          angular.forEach(scope.table.filteredSwitches, function(switch_) {
            SwitchesManager.selectItem(switch_.system_id);
          });
        }
        scope.updateAllChecked();
        scope.onCheckAll();
      };

      // Selects and unselects switch.
      scope.toggleChecked = function(switch_) {
        if (SwitchesManager.isSelected(switch_.system_id)) {
          SwitchesManager.unselectItem(switch_.system_id);
        } else {
          SwitchesManager.selectItem(switch_.system_id);
        }
        scope.updateAllChecked();
        scope.onCheck({ $switch_: switch_ });
      };

      // Sorts the table by predicate.
      scope.sortTable = function(predicate) {
        scope.table.predicate = predicate;
        scope.table.reverse = !scope.table.reverse;
      };

      // Sets the viewable column or sorts.
      scope.selectColumnOrSort = function(predicate) {
        if (scope.table.column !== predicate) {
          scope.table.column = predicate;
        } else {
          scope.sortTable(predicate);
        }
      };

      // Return true if spinner should be shown.
      scope.showSpinner = function(switch_) {
        return SPINNER_STATUSES.indexOf(switch_.status_code) > -1;
      };

      // Returns the release title from osinfo.
      scope.getReleaseTitle = function(os_release) {
        if (angular.isArray(scope.table.osinfo.releases)) {
          for (let i = 0; i < scope.table.osinfo.releases.length; i++) {
            var release = scope.table.osinfo.releases[i];
            if (release[0] === os_release) {
              return release[1];
            }
          }
        }
        return os_release;
      };

      // Returns the status text to show.
      scope.getStatusText = function(switch_) {
        var showRelease = ["Deploying", "Deployed"];
        if (showRelease.indexOf(switch_.status) === -1) {
          return switch_.status;
        } else {
          var releaseTitle = scope.getReleaseTitle(
            switch_.osystem + "/" + switch_.distro_series
          );
          if (switch_.osystem === "ubuntu") {
            releaseTitle = releaseTitle.split('"')[0].trim();
          }
          if (switch_.status === "Deployed") {
            return releaseTitle;
          }
          if (switch_.status === "Deploying") {
            return switch_.status + " " + releaseTitle;
          }
        }
      };

      // When the list of filtered switches change update the all checkbox.
      scope.$watchCollection("table.filteredSwitches", function() {
        scope.updateAllChecked();
        scope.onListingChange({ $switches: scope.table.filteredSwitches });
      });
    }
  };
}

export default maasSwitchesTable;
