/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Machines listing directive.
 *
 * Renders the machines listing.
 */

import { NodeStatus } from "../enum";

/* @ngInject */
function maasMachinesTable(
  MachinesManager,
  NotificationsManager,
  UsersManager,
  GeneralManager,
  $filter,
  $document,
  $window,
  $log
) {
  return {
    restrict: "E",
    scope: {
      loading: "<",
      search: "=",
      groupByLabel: "=",
      actionOption: "=",
      ngDisabled: "&",
      machineHasError: "&",
      hideActions: "=?",
      onListingChange: "&",
      onCheckAll: "&",
      onCheck: "=",
      pools: "=",
      zones: "=",
      hideFailedTests: "<",
      metadata: "="
    },
    templateUrl:
      "static/partials/machines-table.html?v=" +
      $window.MAAS_config.files_version,
    link: function(scope) {
      scope.clickHandler = event => {
        const targetClasses = event.target.classList || [];
        const parentClasses = event.target.parentNode.classList || [];

        if (
          targetClasses.contains("p-table-menu__toggle") ||
          targetClasses.contains("p-double-row__icon-container") ||
          parentClasses.contains("p-table-menu__dropdown") ||
          parentClasses.contains("p-double-row__icon-container")
        ) {
          return;
        }
        scope.$apply(scope.closeMenu);
      };

      $document.on("click", scope.clickHandler);
      scope.$on("$destroy", () => $document.off("click", scope.clickHandler));
    },
    controller: MachinesTableController
  };

  /* @ngInject */
  function MachinesTableController($scope) {
    // Statuses that should show spinner.
    const SPINNER_STATUSES = [
      NodeStatus.COMMISSIONING,
      NodeStatus.DEPLOYING,
      NodeStatus.RELEASING,
      NodeStatus.DISK_ERASING,
      NodeStatus.ENTERING_RESCUE_MODE,
      NodeStatus.EXITING_RESCUE_MODE,
      NodeStatus.TESTING
    ];
    const machines = MachinesManager.getItems();

    // Scope variables.
    $scope.table = {
      column: "fqdn",
      predicate: "fqdn",
      reverse: false,
      allViewableChecked: false,
      machines,
      filteredMachines: machines,
      osinfo: GeneralManager.getData("osinfo"),
      machineActions: GeneralManager.getData("machine_actions")
    };

    $scope.DISPLAY_LIMIT = 5;
    $scope.displayLimits = {};
    const groupLabels = [
      "Failed",
      "New",
      "Commissioning",
      "Testing",
      "Ready",
      "Allocated",
      "Deploying",
      "Deployed",
      "Rescue mode",
      "Releasing",
      "Broken",
      "Other"
    ];

    $scope.getLimit = group => $scope.displayLimits[group.label];

    $scope.loadAll = selectedGroup => {
      $scope.displayLimits[selectedGroup.label] = undefined;
    };

    $scope.statusMenuActions = [
      "commission",
      "acquire",
      "deploy",
      "release",
      "abort",
      "test",
      "rescue-mode",
      "exit-rescue-mode",
      "mark-broken",
      "mark-fixed",
      "override-failed-testing",
      "lock",
      "unlock"
    ];

    $scope.openMenu = "";

    $scope.closedGroups = [];

    $scope.groupBy = (list, keyGetter) => {
      const map = new Map();
      list.forEach(item => {
        const key = keyGetter(item);
        const collection = map.get(key);
        if (!collection) {
          map.set(key, [item]);
        } else {
          collection.push(item);
        }
      });
      return map;
    };

    $scope.getActionSentence = (action, machine) => {
      let name = "machine";
      if (machine && machine.hostname) {
        name = machine.hostname;
      }
      switch (action) {
        case "abort":
          return `abort current action of ${name}`;
        case "acquire":
          return `acquire ${name}`;
        case "check":
          return `check power state of ${name}`;
        case "commission":
          return `commission ${name}`;
        case "deploy":
          return `deploy ${name}`;
        case "exit-rescue-mode":
          return `exit rescue mode of ${name}`;
        case "lock":
          return `lock ${name}`;
        case "mark-broken":
          return `mark ${name} as broken`;
        case "mark-fixed":
          return `mark ${name} as fixed`;
        case "off":
          return `power off ${name}`;
        case "on":
          return `power on ${name}`;
        case "override-failed-testing":
          return `override failed testing of ${name}`;
        case "release":
          return `release ${name}`;
        case "rescue-mode":
          return `enter rescue mode of ${name}`;
        case "set-pool":
          return `set pool of ${name}`;
        case "set-zone":
          return `set zone of ${name}`;
        case "test":
          return `test ${name}`;
        case "unlock":
          return `unlock ${name}`;
        default:
          return "perform action";
      }
    };

    // Ensures that the checkbox for select all is the correct value.
    $scope.updateAllChecked = function() {
      // Not checked when the filtered machines are empty.
      if (
        $scope.table.filteredMachines &&
        $scope.table.filteredMachines.length === 0
      ) {
        $scope.table.allViewableChecked = false;
        return;
      }

      // Loop through all filtered machines and see if all are checked.
      var i;
      for (i = 0; i < $scope.table.filteredMachines.length; i++) {
        if (!$scope.table.filteredMachines[i].$selected) {
          $scope.table.allViewableChecked = false;
          return;
        }
      }
      $scope.table.allViewableChecked = true;
    };

    // Selects and deselects visible machines.
    $scope.toggleCheckAll = function() {
      if ($scope.table.allViewableChecked) {
        angular.forEach($scope.table.filteredMachines, function(machine) {
          MachinesManager.unselectItem(machine.system_id);
        });
      } else {
        angular.forEach($scope.table.filteredMachines, function(machine) {
          MachinesManager.selectItem(machine.system_id);
        });
      }
      $scope.updateFilteredMachines();
      $scope.updateAllChecked();
      $scope.onCheckAll();
    };

    // Selects and unselects machine.
    $scope.toggleChecked = function(machine) {
      if (MachinesManager.isSelected(machine.system_id)) {
        MachinesManager.unselectItem(machine.system_id);
      } else {
        MachinesManager.selectItem(machine.system_id);
      }
      $scope.updateFilteredMachines();
      $scope.updateAllChecked();
    };

    $scope.toggleCheckGroup = groupLabel => {
      const machineGroup = $scope.groupedMachines.find(group => {
        return group.label === groupLabel;
      });
      if ($scope.getGroupSelectedState(groupLabel)) {
        machineGroup.machines.forEach(machine => {
          MachinesManager.unselectItem(machine.system_id);
        });
      } else {
        machineGroup.machines.forEach(machine => {
          MachinesManager.selectItem(machine.system_id);
        });
      }
      $scope.updateFilteredMachines();
      $scope.updateAllChecked();
    };

    $scope.toggleOpenGroup = groupLabel => {
      if ($scope.closedGroups.includes(groupLabel)) {
        $scope.closedGroups = $scope.closedGroups.filter(
          group => group !== groupLabel
        );
      } else {
        $scope.closedGroups = [...$scope.closedGroups, groupLabel];
      }
    };

    // Sorts the table by predicate.
    $scope.sortTable = function(predicate) {
      $scope.table.predicate = predicate;
      $scope.table.reverse = !$scope.table.reverse;
    };

    // Sets the viewable column or sorts.
    $scope.selectColumnOrSort = function(predicate) {
      if ($scope.table.column !== predicate) {
        $scope.table.column = predicate;
      } else {
        $scope.sortTable(predicate);
      }
    };

    // Return true if spinner should be shown.
    $scope.showSpinner = function(machine) {
      return SPINNER_STATUSES.indexOf(machine.status_code) > -1;
    };

    $scope.showFailedTestWarning = function(machine) {
      if ($scope.showSpinner(machine)) {
        return false;
      }
      switch (machine.status_code) {
        case NodeStatus.NEW:
        // fall through
        case NodeStatus.COMMISSIONING:
        // fall through
        case NodeStatus.FAILED_COMMISSIONING:
        // fall through
        case NodeStatus.TESTING:
        // fall through
        case NodeStatus.FAILED_TESTING:
          return false;
      }
      switch (machine.testing_status.status) {
        // Tests haven't been run
        case -1:
        // Tests have passed
        // fall through
        case 2:
          return false;
      }
      return true;
    };

    // Return true if the other node status should be shown.
    $scope.showNodeStatus = function(machine) {
      // -1 means tests haven't been run, 2 means tests have passed.
      if (
        !$scope.showSpinner(machine) &&
        !$scope.showFailedTestWarning(machine) &&
        machine.other_test_status.status !== -1 &&
        machine.other_test_status.status !== 2
      ) {
        return true;
      } else {
        return false;
      }
    };

    // Returns the release title from osinfo.
    $scope.getReleaseTitle = function(os_release) {
      if (angular.isArray($scope.table.osinfo.releases)) {
        for (let i = 0; i < $scope.table.osinfo.releases.length; i++) {
          var release = $scope.table.osinfo.releases[i];
          if (release[0] === os_release) {
            return release[1];
          }
        }
      }
      return os_release;
    };

    // Returns the status text to show.
    $scope.getStatusText = function(machine) {
      var showRelease = ["Deploying", "Deployed"];
      if (showRelease.indexOf(machine.status) === -1) {
        return machine.status;
      } else {
        var releaseTitle = $scope.getReleaseTitle(
          machine.osystem + "/" + machine.distro_series
        );
        if (machine.osystem === "ubuntu") {
          releaseTitle = releaseTitle.split('"')[0].trim();
        }
        if (machine.status === "Deployed") {
          return releaseTitle;
        }
        if (machine.status === "Deploying") {
          return machine.status + " " + releaseTitle;
        }
      }
    };

    // Returns the status message to show.
    $scope.getStatusMessage = function(machine) {
      var showMessage = [1, 9, 12, 14, 17, 19, 21];
      if (showMessage.indexOf(machine.status_code) >= 0) {
        return machine.status_message;
      } else {
        return "";
      }
    };

    $scope.getSpacesTooltipMessage = spaces => {
      var spacesMessage = "";

      if (spaces.length > 1) {
        spaces.forEach((space, index) => {
          spacesMessage += space;

          if (index !== spaces.length - 1) {
            spacesMessage += "\n";
          }
        });
      }

      return spacesMessage;
    };

    $scope.getGroupSelectedState = groupLabel => {
      const machineGroup = $scope.groupedMachines.find(group => {
        return group.label === groupLabel;
      });
      return !machineGroup.machines.some(machine => !machine.$selected);
    };

    $scope.getGroupCountString = groupLabel => {
      const machineGroup = $scope.groupedMachines.find(group => {
        return group.label === groupLabel;
      });
      const machines = machineGroup.machines.length;
      const selected = machineGroup.machines.filter(item => item.$selected)
        .length;
      const machinesString = `${machines} ${
        machines === 1 ? "machine" : "machines"
      }`;

      if (selected && selected === machines) {
        return `${machinesString} selected`;
      }
      return `${machinesString}${selected ? `, ${selected} selected` : ""}`;
    };

    $scope.updateGroupedMachines = function(field) {
      if (field === "none") {
        $scope.noGrouping = true;
      } else {
        $scope.noGrouping = false;
      }
      if (field === "status") {
        const machines = $scope.groupBy(
          $scope.table.filteredMachines,
          machine => machine.status_code
        );
        $scope.groupedMachines = [
          {
            label: "Failed",
            machines: [
              ...(machines.get(NodeStatus.FAILED_COMMISSIONING) || []),
              ...(machines.get(NodeStatus.FAILED_DEPLOYMENT) || []),
              ...(machines.get(NodeStatus.FAILED_RELEASING) || []),
              ...(machines.get(NodeStatus.FAILED_DISK_ERASING) || []),
              ...(machines.get(NodeStatus.FAILED_ENTERING_RESCUE_MODE) || []),
              ...(machines.get(NodeStatus.FAILED_EXITING_RESCUE_MODE) || []),
              ...(machines.get(NodeStatus.FAILED_TESTING) || [])
            ]
          },
          {
            label: "New",
            machines: [...(machines.get(NodeStatus.NEW) || [])]
          },
          {
            label: "Commissioning",
            machines: [...(machines.get(NodeStatus.COMMISSIONING) || [])]
          },
          {
            label: "Testing",
            machines: [...(machines.get(NodeStatus.TESTING) || [])]
          },
          {
            label: "Ready",
            machines: [...(machines.get(NodeStatus.READY) || [])]
          },
          {
            label: "Allocated",
            machines: [...(machines.get(NodeStatus.ALLOCATED) || [])]
          },
          {
            label: "Deploying",
            machines: [...(machines.get(NodeStatus.DEPLOYING) || [])]
          },
          {
            label: "Deployed",
            machines: [...(machines.get(NodeStatus.DEPLOYED) || [])]
          },
          {
            label: "Rescue mode",
            machines: [
              ...(machines.get(NodeStatus.RESCUE_MODE) || []),
              ...(machines.get(NodeStatus.ENTERING_RESCUE_MODE) || []),
              ...(machines.get(NodeStatus.EXITING_RESCUE_MODE) || [])
            ]
          },
          {
            label: "Releasing",
            machines: [
              ...(machines.get(NodeStatus.RELEASING) || []),
              ...(machines.get(NodeStatus.DISK_ERASING) || [])
            ]
          },
          {
            label: "Broken",
            machines: [...(machines.get(NodeStatus.BROKEN) || [])]
          },
          {
            label: "Other",
            machines: [
              ...(machines.get(NodeStatus.RETIRED) || []),
              ...(machines.get(NodeStatus.MISSING) || []),
              ...(machines.get(NodeStatus.RESERVED) || [])
            ]
          }
        ];
        groupLabels.forEach(label => {
          $scope.displayLimits[label] = $scope.DISPLAY_LIMIT;
        });
        return;
      }

      if (field === "owner") {
        const grouped = $scope.groupBy(
          $scope.table.filteredMachines,
          machine => machine.owner
        );

        const groupedByOwner = Array.from(grouped).map(([label, machines]) => {
          if (label == "") {
            label = "No owner";
          }
          return {
            label,
            machines
          };
        });

        $scope.groupedMachines = groupedByOwner;
        groupedByOwner.forEach(owner => {
          $scope.displayLimits[owner.label] = $scope.DISPLAY_LIMIT;
        });
        return;
      }

      $scope.groupedMachines = [
        {
          label: "none",
          machines: $scope.table.filteredMachines
        }
      ];
      $scope.displayLimits["none"] = $scope.DISPLAY_LIMIT;
      return;
    };

    $scope.updateFilteredMachines = () => {
      $scope.table.filteredMachines = $filter("nodesFilter")(
        $scope.table.machines,
        $scope.search
      );
      $scope.displayLimits["none"] = $scope.DISPLAY_LIMIT;
    };

    // When the list of filtered machines change update the all checkbox.
    $scope.$watchCollection("table.filteredMachines", function() {
      $scope.updateAllChecked();
      $scope.onListingChange({ $machines: $scope.table.filteredMachines });
      $scope.updateGroupedMachines($scope.groupByLabel);
    });

    $scope.$watch("groupByLabel", function() {
      $scope.updateGroupedMachines($scope.groupByLabel);
    });

    $scope.$watch("search", $scope.updateFilteredMachines);

    // Watch simplified list of machines for changes to power state and status,
    // then make changes accordingly.
    $scope.$watch(
      scope =>
        scope.table.machines.map(machine => ({
          id: machine.id,
          status: machine.status,
          state: machine.power_state
        })),
      (newMachines, oldMachines) => {
        newMachines.forEach(newMachine => {
          const oldMachine =
            oldMachines.find(machine => machine.id === newMachine.id) || {};

          // Check if power state has changed, then set transitional state
          if (newMachine.state !== oldMachine.state) {
            $scope.table.machines.find(
              machine => machine.id === newMachine.id
            ).powerTransition = undefined;
          }

          // Check if status has changed, then run function to regroup machines
          // if machines have been loaded
          if (
            newMachine.status !== oldMachine.status &&
            $scope.groupByLabel !== "none" &&
            !$scope.loading
          ) {
            $scope.updateGroupedMachines($scope.groupByLabel);
          }
        });
      },
      true
    );

    // Truncates leading zeroes in RAM and returns unit separately
    $scope.formatMemoryUnit = function(ram) {
      var memory = parseFloat(ram);
      return {
        value: memory.toString(),
        unit: "GiB"
      };
    };

    // Converts GB into TB if necessary and output three sig-figs
    $scope.formatStorageUnit = function(gb) {
      var storage = parseFloat(gb);
      if (storage < 1000) {
        return {
          value: Number(storage.toPrecision(3)).toString(),
          unit: "GB"
        };
      } else {
        return {
          value: Number((storage / 1000).toPrecision(3)).toString(),
          unit: "TB"
        };
      }
    };

    $scope.getCheckboxClass = function(node) {
      if ($scope.actionOption) {
        if (
          node.$selected &&
          node.actions.indexOf($scope.actionOption.name) > -1
        ) {
          return "actionable";
        }
        return "not-actionable";
      }
      return "";
    };

    $scope.getAllCheckboxClass = function(nodes) {
      if (nodes && $scope.actionOption) {
        for (var i = 0; i < nodes.length; i++) {
          if (nodes[i].actions.indexOf($scope.actionOption.name) === -1) {
            return "not-actionable";
          }
        }
        return "actionable";
      }
      return "";
    };

    $scope.getBootIp = function(ipArray) {
      for (var i = 0; i < ipArray.length; i++) {
        if (ipArray[i].is_boot) {
          return ipArray[i].ip;
        }
      }
      return false;
    };

    $scope.removeDuplicates = function(ipArray, prop) {
      if (!angular.isArray(ipArray)) {
        return;
      }

      return ipArray.filter((obj, pos, arr) => {
        return arr.map(mapObj => mapObj[prop]).indexOf(obj[prop]) === pos;
      });
    };

    $scope.changePowerState = (machine, action) => {
      $scope.closeMenu();
      machine.powerTransition = true;

      if (action === "check") {
        MachinesManager.checkPowerState(machine).then(
          () => {
            machine.action_failed = false;
            machine.powerTransition = undefined;
          },
          error => {
            $scope.createErrorNotification(machine, action, error);
            machine.action_failed = true;
            machine.powerTransition = undefined;
          }
        );
      } else {
        MachinesManager.performAction(machine, action).then(
          () => {
            machine.action_failed = false;
          },
          error => {
            $scope.createErrorNotification(machine, action, error);
            machine.action_failed = true;
            machine.powerTransition = undefined;
          }
        );
      }
    };

    $scope.performAction = (machine, action, extra) => {
      $scope.closeMenu();
      machine[`${action}-transition`] = true;

      if (!angular.isObject(extra)) {
        extra = {};
      }

      MachinesManager.performAction(machine, action, extra).then(
        () => {
          machine.action_failed = false;
        },
        error => {
          $scope.createErrorNotification(machine, action, error);
          machine.action_failed = true;
          machine[`${action}-transition`] = undefined;
        }
      );
    };

    $scope.getActionTitle = actionName => {
      const { table } = $scope;
      const { machineActions, osinfo } = table;

      // Display default OS and release if in-table action is "deploy"
      if (actionName === "deploy" && osinfo) {
        const { osystems, releases, default_osystem, default_release } = osinfo;
        const os = osystems && osystems.find(os => os[0] === default_osystem);
        const release =
          releases &&
          releases.find(
            release => release[0] === `${default_osystem}/${default_release}`
          );
        if (os && release) {
          return `Deploy ${os[1]} ${release[1]}...`;
        }
        return `Deploy ${default_osystem}/${default_release}...`;
      }

      // Otherwise, just display the action's title
      if (machineActions.length) {
        return machineActions.find(action => action.name === actionName).title;
      }
    };

    $scope.getStatusActions = machine => {
      return $scope.statusMenuActions.filter(action =>
        machine.actions.includes(action)
      );
    };

    $scope.toggleMenu = menu => {
      $scope.openMenu = $scope.openMenu === menu ? "" : menu;
    };

    $scope.closeMenu = () => ($scope.openMenu = "");

    $scope.getArchitectureText = architectureString => {
      if (architectureString.includes("/generic")) {
        return architectureString.split("/")[0];
      } else {
        return architectureString;
      }
    };

    $scope.createErrorNotification = (machine, action, error) => {
      const authUser = UsersManager.getAuthUser();
      if (angular.isObject(authUser)) {
        NotificationsManager.createItem({
          message: `Unable to ${$scope.getActionSentence(
            action,
            machine
          )}: ${error}`,
          category: "error",
          user: authUser.id
        });
      } else {
        $log.error(error);
      }
    };
  }
}

export default maasMachinesTable;
