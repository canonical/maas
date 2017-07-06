/* Copyright 2017 Canonical Ltd.  This software is licensed under the
* GNU Affero General Public License version 3 (see the file LICENSE).
*
* Machines listing directive.
*
* Renders the machines listing.
*/
// testing



angular.module('MAAS').directive('maasMachinesTable', [
  'MachinesManager', 'GeneralManager', 'ManagerHelperService',
  function (MachinesManager, GeneralManager, ManagerHelperService) {
    return {
      restrict: "E",
      scope: {
        search: "=",
        ngDisabled: "&",
        machineHasError: "&",
        hideCheckboxes: "=?",
        onListingChange: "&",
        onCheckAll: "&",
        onCheck: "&"
      },
      templateUrl: (
        'static/partials/machines-table.html?v=' + (
          MAAS_config.files_version)),
      link: function(scope, element, attrs) {
        // Statuses that should show spinner.
        var SPINNER_STATUSES = [
          1,   // commissioning
          9,   // deploying
          12,  // releasing
          14,  // disk erasing
          17,  // entering rescue mode
          19,  // exiting rescue mode
          21   // testing
        ];

        // Scope variables.
        scope.table = {
          column: 'fqdn',
          predicate: 'fqdn',
          reverse: false,
          allViewableChecked: false,
          machines: MachinesManager.getItems(),
          filteredMachines: [],
          osinfo: GeneralManager.getData("osinfo")
        };

        // Ensures that the checkbox for select all is the correct value.
        scope.updateAllChecked = function() {
          // Not checked when the filtered machines are empty.
          if(scope.table.filteredMachines.length === 0) {
              scope.table.allViewableChecked = false;
              return;
          }

          // Loop through all filtered machines and see if all are checked.
          var i;
          for(i = 0; i < scope.table.filteredMachines.length; i++) {
              if(!scope.table.filteredMachines[i].$selected) {
                  scope.table.allViewableChecked = false;
                  return;
              }
          }
          scope.table.allViewableChecked = true;
        };

        // Selects and deselects visible machines.
        scope.toggleCheckAll = function() {
          if(scope.table.allViewableChecked) {
            angular.forEach(
              scope.table.filteredMachines, function(machine) {
                MachinesManager.unselectItem(machine.system_id);
              });
          } else {
            angular.forEach(
              scope.table.filteredMachines, function(machine) {
                MachinesManager.selectItem(machine.system_id);
              });
          }
          scope.updateAllChecked();
          scope.onCheckAll();
        };

        // Selects and unselects machine.
        scope.toggleChecked = function(machine) {
          if(MachinesManager.isSelected(machine.system_id)) {
            MachinesManager.unselectItem(machine.system_id);
          } else {
            MachinesManager.selectItem(machine.system_id);
          }
          scope.updateAllChecked();
          scope.onCheck({$machine: machine});
        };

        // Sorts the table by predicate.
        scope.sortTable = function(predicate) {
            scope.table.predicate = predicate;
            scope.table.reverse = !scope.table.reverse;
        };

        // Sets the viewable column or sorts.
        scope.selectColumnOrSort = function(predicate) {
            if(scope.table.column !== predicate) {
                scope.table.column = predicate;
            } else {
                scope.sortTable(predicate);
            }
        };

        // Return true if spinner should be shown.
        scope.showSpinner = function(machine) {
          return SPINNER_STATUSES.indexOf(machine.status_code) > -1;
        };

        // Returns the release title from osinfo.
        scope.getReleaseTitle = function(os_release) {
          if(angular.isArray(scope.table.osinfo.releases)) {
            for(i = 0; i < scope.table.osinfo.releases.length; i++) {
              var release = scope.table.osinfo.releases[i];
              if(release[0] === os_release) {
                return release[1];
              }
            }
          }
          return os_release;
        };

        // Returns the status text to show.
        scope.getStatusText = function(machine) {
          var showRelease = ['Deploying', 'Deployed'];
          if(showRelease.indexOf(machine.status) === -1) {
            return machine.status;
          } else {
            var releaseTitle = scope.getReleaseTitle(
              machine.osystem + '/' + machine.distro_series);
            if(machine.osystem === "ubuntu") {
              releaseTitle = releaseTitle.split('"')[0].trim();
            }
            if(machine.status === "Deployed") {
              return releaseTitle;
            }
            if(machine.status === "Deploying") {
              return machine.status + ' ' + releaseTitle;
            }
          }
        };

        // When the list of filtered machines change update the all checkbox.
        scope.$watchCollection("table.filteredMachines", function() {
          scope.updateAllChecked();
          scope.onListingChange({$machines: scope.table.filteredMachines});
        });

        // Load the required managers and start polling for osinfo.
        ManagerHelperService.loadManagers(
          scope, [MachinesManager, GeneralManager]).then(function() {
            GeneralManager.startPolling(scope, "osinfo");
          });

        // Stop polling when the scope is destroyed.
        scope.$on("$destroy", function() {
          GeneralManager.stopPolling(scope, "osinfo");
        });
      }
    };
}]);
