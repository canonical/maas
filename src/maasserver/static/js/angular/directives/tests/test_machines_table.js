/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for machines table directive.
 */

import { makeName } from "testing/utils";

describe("maasMachinesTable", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Preload the $templateCache with empty contents. We only test the
  // controller of the directive, not the template.
  var $q, $templateCache;
  beforeEach(inject(function($injector) {
    $q = $injector.get("$q");
    $templateCache = $injector.get("$templateCache");
    $templateCache.put("static/partials/machines-table.html?v=undefined", "");
  }));

  // Load the required managers.
  var MachinesManager, GeneralManager, NotificationsManager, UsersManager;
  beforeEach(inject(function($injector) {
    MachinesManager = $injector.get("MachinesManager");
    NotificationsManager = $injector.get("NotificationsManager");
    UsersManager = $injector.get("UsersManager");
    GeneralManager = $injector.get("GeneralManager");
  }));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Makes a machine.
  function makeMachine() {
    var machine = {
      system_id: makeName("system_id"),
      hostname: makeName("name"),
      $selected: false
    };
    MachinesManager._items.push(machine);
    return machine;
  }

  // Make OS choice.
  function makeOS() {
    const name = makeName("os");
    return [name, name.toUpperCase()];
  }

  // Make release choice for OS.
  function makeRelease(os) {
    const release = makeName("release");
    const osRelease = os[0] + "/" + release;
    return [osRelease, release];
  }

  // Return the compiled directive with the items from the scope.
  function compileDirective(design) {
    var directive;
    var html = [
      "<div>",
      "<maas-machines-table ",
      'on-listing-change="onListingChange($machines)" ',
      'on-check-all="onCheckAll()" ',
      'on-check="onCheck($machine)"></maas-machines-table>',
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("maas-machines-table");
  }

  it("sets initial variables", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    expect(scope.table).toEqual({
      column: "fqdn",
      predicate: "fqdn",
      reverse: false,
      allViewableChecked: false,
      machines: MachinesManager.getItems(),
      filteredMachines: MachinesManager.getItems(),
      osinfo: GeneralManager.getData("osinfo"),
      machineActions: GeneralManager.getData("machine_actions")
    });
    expect(scope.table.machines).toBe(MachinesManager.getItems());
  });

  describe("updateAllChecked", function() {
    it("sets allViewableChecked to false when no machines", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.table.allViewableChecked = true;
      scope.table.filteredMachines = [];
      scope.updateAllChecked();
      expect(scope.table.allViewableChecked).toBe(false);
    });

    it("sets allViewableChecked to false when one not selected", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.table.allViewableChecked = true;
      scope.table.filteredMachines = [
        {
          $selected: true
        },
        {
          $selected: false
        }
      ];
      scope.updateAllChecked();
      expect(scope.table.allViewableChecked).toBe(false);
    });

    it("sets allViewableChecked to false when one not selected", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.table.filteredMachines = [
        {
          $selected: true
        },
        {
          $selected: true
        }
      ];
      scope.updateAllChecked();
      expect(scope.table.allViewableChecked).toBe(true);
    });
  });

  describe("toggleCheckAll", function() {
    it("unselected all selected machines", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var machine = makeMachine();
      MachinesManager.selectItem(machine.system_id);
      scope.table.allViewableChecked = true;
      scope.table.filteredMachines = [machine];
      scope.toggleCheckAll();
      expect(machine.$selected).toBe(false);
      expect(scope.table.allViewableChecked).toBe(false);
    });

    it("selects all unselected machines", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var machine = makeMachine();
      scope.table.allViewableChecked = false;
      scope.table.filteredMachines = [machine];
      scope.toggleCheckAll();
      expect(machine.$selected).toBe(true);
      expect(scope.table.allViewableChecked).toBe(true);
    });

    it("calls onCheckAll", function() {
      $scope.onCheckAll = jasmine.createSpy("onCheckAll");
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.toggleCheckAll();
      expect($scope.onCheckAll).toHaveBeenCalled();
    });
  });

  describe("toggleCheckGroup", () => {
    it("selects all unselected machines in a group", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();

      const machines = [makeMachine(), makeMachine(), makeMachine()];
      machines[0].status = "New";
      machines[1].status = "Broken";
      machines[2].status = "New";
      scope.table.filteredMachines = machines;
      scope.groupedMachines = [
        { label: "New", machines: [machines[0], machines[2]] },
        { label: "Broken", machines: [machines[1]] }
      ];
      scope.toggleCheckGroup("New");

      expect(machines[0].$selected).toBe(true);
      expect(machines[1].$selected).toBe(false);
      expect(machines[2].$selected).toBe(true);
    });

    it("unselects all machines in a group if all are selected", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();

      const machines = [makeMachine(), makeMachine(), makeMachine()];
      machines[0].status = "New";
      machines[0].$selected = true;
      machines[1].status = "Broken";
      machines[1].$selected = true;
      machines[2].status = "New";
      machines[2].$selected = true;
      scope.table.filteredMachines = machines;
      scope.groupedMachines = [
        { label: "New", machines: [machines[0], machines[2]] },
        { label: "Broken", machines: [machines[1]] }
      ];
      scope.toggleCheckGroup("New");

      expect(machines[0].$selected).toBe(false);
      expect(machines[1].$selected).toBe(true);
      expect(machines[2].$selected).toBe(false);
    });
  });

  describe("toggleChecked", function() {
    it("selects machine", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var machine = makeMachine();
      scope.table.filteredMachines = [machine];
      scope.toggleChecked(machine);
      expect(machine.$selected).toBe(true);
      expect(scope.table.allViewableChecked).toBe(true);
    });

    it("unselects machine", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var machine = makeMachine();
      scope.table.filteredMachines = [machine];
      MachinesManager.selectItem(machine.system_id);
      scope.toggleChecked(machine);
      expect(machine.$selected).toBe(false);
      expect(scope.table.allViewableChecked).toBe(false);
    });
  });

  describe("toggleOpenGroup", () => {
    it("removes group from scope.closedGroups if present", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const group = makeName("group");
      scope.closedGroups = [group];
      scope.toggleOpenGroup(group);
      expect(scope.closedGroups).toEqual([]);
    });

    it("adds group to scope.closedGroups if not present", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const group = makeName("group");
      scope.closedGroups = [];
      scope.toggleOpenGroup(group);
      expect(scope.closedGroups).toEqual([group]);
    });
  });

  describe("sortTable", function() {
    it("sets predicate", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var predicate = makeName("predicate");
      scope.sortTable(predicate);
      expect(scope.table.predicate).toBe(predicate);
    });

    it("reverses reverse", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.table.reverse = true;
      scope.sortTable(makeName("predicate"));
      expect(scope.table.reverse).toBe(false);
    });
  });

  describe("selectColumnOrSort", function() {
    it("sets column if different", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var column = makeName("column");
      scope.selectColumnOrSort(column);
      expect(scope.table.column).toBe(column);
    });

    it("calls sortTable if column already set", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var column = makeName("column");
      scope.table.column = column;
      spyOn(scope, "sortTable");
      scope.selectColumnOrSort(column);
      expect(scope.sortTable).toHaveBeenCalledWith(column);
    });
  });

  describe("showSpinner", function() {
    it("returns false/true based on status codes", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var STATUSES = [1, 9, 12, 14, 17, 19];
      var i;
      for (i = 0; i < 20; i++) {
        var machine = {
          status_code: i
        };
        var expected = false;
        if (STATUSES.indexOf(i) > -1) {
          expected = true;
        }
        expect(scope.showSpinner(machine)).toBe(expected);
      }
    });
  });

  describe("showFailedTestWarning", function() {
    var spinner_statuses = [0, 1, 2, 21, 22];
    var testing_statuses = [-1, 2];

    it("returns false when showing spinner", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "showSpinner").and.returnValue(true);
      expect(scope.showFailedTestWarning({})).toBe(false);
    });

    it("returns false when testing or commissioning", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "showSpinner").and.returnValue(false);
      angular.forEach(spinner_statuses, function(status) {
        var machine = {
          status_code: status
        };
        expect(scope.showFailedTestWarning(machine)).toBe(false);
      });
    });

    it("returns false when testing_status is passed/unknown", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "showSpinner").and.returnValue(false);
      angular.forEach(testing_statuses, function(testing_status) {
        var machine = {
          status_code: 4, // READY
          testing_status: { status: testing_status }
        };
        expect(scope.showFailedTestWarning(machine)).toBe(false);
      });
    });

    it("returns true otherwise", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "showSpinner").and.returnValue(false);
      var i, j;
      // Go through all known statuses
      for (i = 0; i <= 22; i++) {
        if (spinner_statuses.indexOf(i) === -1) {
          // Go through all known script statuses
          for (j = -1; j <= 8; j++) {
            if (testing_statuses.indexOf(j) === -1) {
              var machine = {
                status_code: i,
                testing_status: { status: j }
              };
              expect(scope.showFailedTestWarning(machine)).toBe(true);
            }
          }
        }
      }
    });
  });

  describe("showNodeStatus", function() {
    it("returns false when showing spinner", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "showSpinner").and.returnValue(true);
      spyOn(scope, "showFailedTestWarning").and.returnValue(false);
      var machine = {
        other_test_status: { status: 3 }
      };
      expect(scope.showNodeStatus(machine)).toBe(false);
    });

    it("returns false when showing failed test warning", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "showSpinner").and.returnValue(false);
      spyOn(scope, "showFailedTestWarning").and.returnValue(true);
      var machine = {
        other_test_status: { status: 3 }
      };
      expect(scope.showNodeStatus(machine)).toBe(false);
    });

    it("returns false when other_test_status is passed", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "showSpinner").and.returnValue(false);
      spyOn(scope, "showFailedTestWarning").and.returnValue(false);
      var machine = {
        other_test_status: { status: 2 }
      };
      expect(scope.showNodeStatus(machine)).toBe(false);
    });

    it("returns true otherwise", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "showSpinner").and.returnValue(false);
      spyOn(scope, "showFailedTestWarning").and.returnValue(false);
      var machine = {
        other_test_status: { status: 3 }
      };
      expect(scope.showNodeStatus(machine)).toBe(true);
    });
  });

  describe("getReleaseTitle", function() {
    it("returns release title from osinfo", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.table.osinfo = {
        releases: [["ubuntu/xenial", "Ubuntu Xenial"]]
      };
      expect(scope.getReleaseTitle("ubuntu/xenial")).toBe("Ubuntu Xenial");
    });

    it("returns release name when not in osinfo", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.table.osinfo = {
        releases: []
      };
      expect(scope.getReleaseTitle("ubuntu/xenial")).toBe("ubuntu/xenial");
    });

    it("returns release name when osinfo.releases undefined", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.table.osinfo = {};
      expect(scope.getReleaseTitle("ubuntu/xenial")).toBe("ubuntu/xenial");
    });
  });

  describe("getStatusText", function() {
    it("returns status text when not deployed or deploying", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var machine = {
        status: makeName("status")
      };

      expect(scope.getStatusText(machine)).toBe(machine.status);
    });

    it("returns status with release title when deploying", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var machine = {
        status: "Deploying",
        osystem: "ubuntu",
        distro_series: "xenial"
      };
      scope.table.osinfo = {
        releases: [["ubuntu/xenial", "Ubuntu Xenial"]]
      };
      expect(scope.getStatusText(machine)).toBe("Deploying Ubuntu Xenial");
    });

    it("returns release title when deployed", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var machine = {
        status: "Deployed",
        osystem: "ubuntu",
        distro_series: "xenial"
      };
      scope.table.osinfo = {
        releases: [["ubuntu/xenial", "Ubuntu Xenial"]]
      };
      expect(scope.getStatusText(machine)).toBe("Ubuntu Xenial");
    });

    it("returns release title without codename when deployed", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var machine = {
        status: "Deployed",
        osystem: "ubuntu",
        distro_series: "xenial"
      };
      scope.table.osinfo = {
        releases: [["ubuntu/xenial", 'Ubuntu 16.04 LTS "Xenial Xerus"']]
      };
      expect(scope.getStatusText(machine)).toBe("Ubuntu 16.04 LTS");
    });
  });

  describe("getStatusMessage", function() {
    angular.forEach([1, 9, 12, 14, 17, 19, 21], function(code) {
      it("returns status message when status code: " + code, function() {
        var directive = compileDirective();
        var scope = directive.isolateScope();
        var machine = {
          status_code: code,
          status_message: makeName("message")
        };

        expect(scope.getStatusMessage(machine)).toBe(machine.status_message);
      });
    });

    it("returns blank when status code not in above list", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var machine = {
        status_code: 2,
        status_message: makeName("message")
      };

      expect(scope.getStatusMessage(machine)).toBe("");
    });
  });

  describe("onListingChange", function() {
    it("called when filteredMachines changes", function() {
      $scope.onListingChange = jasmine.createSpy("onListingChange");
      var directive = compileDirective();
      var scope = directive.isolateScope();

      var machines = [{}];
      scope.table.filteredMachines = machines;

      $scope.$digest();
      expect($scope.onListingChange).toHaveBeenCalledWith(machines);
    });
  });

  describe("formatMemoryUnit", function() {
    it("returns unit and value separately", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var memory = Math.floor(Math.random() * 10) + 1;
      var formattedMemory = scope.formatMemoryUnit(memory);

      var actual = Object.keys(formattedMemory).sort();
      var expected = ["unit", "value"];
      expect(actual).toEqual(expected);
    });

    it("removes leading zeroes and converts to string", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var rand = Math.floor(Math.random() * 10) + 1;
      var memory = rand.toFixed(1);

      var actual = scope.formatMemoryUnit(memory).value;
      var expected = rand.toString();
      expect(actual).toEqual(expected);
    });
  });

  describe("formatStorageUnit", function() {
    it("returns unit and value separately", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var storage = Math.random().toFixed(1) * 100;
      var formattedStorage = scope.formatStorageUnit(storage);

      var actual = Object.keys(formattedStorage).sort();
      var expected = ["unit", "value"];
      expect(actual).toEqual(expected);
    });

    it("displays three significant figures", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var storage = Math.random() * 10;

      var actual = scope.formatStorageUnit(storage).value;
      var expected = Number(storage.toPrecision(3)).toString();
      expect(actual).toEqual(expected);
    });

    it("converts unit to TB at or above 1000 GB", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var storage = 1000.0;

      var actual = scope.formatStorageUnit(storage);
      var expected = {
        unit: "TB",
        value: "1"
      };
      expect(actual).toEqual(expected);
    });
  });

  describe("getBootIp", function() {
    it("returns the machine's boot IP address if it exists", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var ipAddresses = [
        {
          ip: "172.168.1.1",
          is_boot: false
        },
        {
          ip: "172.168.1.2",
          is_boot: true
        }
      ];

      var actual = scope.getBootIp(ipAddresses);
      var expected = "172.168.1.2";
      expect(actual).toEqual(expected);
    });
  });

  describe("removeDuplicates", function() {
    it("returns a unique IP object with a duplicate", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var ipAddresses = [
        {
          ip: "172.168.1.1",
          is_boot: false
        },
        {
          ip: "172.168.1.2",
          is_boot: true
        },
        {
          ip: "172.168.1.2",
          is_boot: true
        }
      ];

      var actual = scope.removeDuplicates(ipAddresses, "ip");
      expect(actual.length).toEqual(2);
    });

    it("returns a unique IP object without a duplicate", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var ipAddresses = [
        {
          ip: "172.168.1.1",
          is_boot: false
        },
        {
          ip: "172.168.1.2",
          is_boot: true
        },
        {
          ip: "172.168.1.3",
          is_boot: true
        }
      ];

      var actual = scope.removeDuplicates(ipAddresses, "ip");
      expect(actual.length).toEqual(3);
    });
  });

  describe("changePowerState", function() {
    it(`executes MachinesManager.checkPowerState
            if action param is "check"`, () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machine = makeMachine();
      const defer = $q.defer();

      spyOn(MachinesManager, "checkPowerState").and.returnValue(defer.promise);

      scope.changePowerState(machine, "check");
      expect(MachinesManager.checkPowerState).toHaveBeenCalledWith(machine);
    });

    it(`creates an error notification for current user
            if 'check' promise rejected`, () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machine = makeMachine();
      const user = { id: 1 };
      const defer = $q.defer();
      const errorMsg = "Everything is broken";

      spyOn(MachinesManager, "checkPowerState").and.returnValue(defer.promise);
      spyOn(NotificationsManager, "createItem").and.returnValue(true);
      spyOn(UsersManager, "getAuthUser").and.returnValue(user);

      scope.changePowerState(machine, "check");
      defer.reject(errorMsg);
      scope.$digest();
      expect(NotificationsManager.createItem).toHaveBeenCalledWith({
        message: `Unable to check power state of ${
          machine.hostname
        }: ${errorMsg}`,
        category: "error",
        user: user.id
      });
    });

    it("executes MachinesManager.performAction correctly", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machine = makeMachine();
      const defer = $q.defer();
      spyOn(MachinesManager, "performAction").and.returnValue(defer.promise);

      scope.changePowerState(machine, "on");
      expect(MachinesManager.performAction).toHaveBeenCalledWith(machine, "on");
    });

    it(`creates an error notification for current user
            if action promise rejected`, () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machine = makeMachine();
      const user = { id: 1 };
      const defer = $q.defer();
      const errorMsg = "Everything is broken";

      spyOn(MachinesManager, "performAction").and.returnValue(defer.promise);
      spyOn(NotificationsManager, "createItem").and.returnValue(true);
      spyOn(UsersManager, "getAuthUser").and.returnValue(user);

      scope.changePowerState(machine, "on");
      defer.reject(errorMsg);
      scope.$digest();
      expect(NotificationsManager.createItem).toHaveBeenCalledWith({
        message: `Unable to power on ${machine.hostname}: ${errorMsg}`,
        category: "error",
        user: user.id
      });
    });
  });

  describe("performAction", function() {
    it("closes any open menus when run", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machine = makeMachine();
      const action = "on";
      const defer = $q.defer();
      spyOn(MachinesManager, "performAction").and.returnValue(defer.promise);

      scope.performAction(machine, action);
      expect(scope.openMenu).toEqual("");
    });

    it("sets machine's action transitional state to true", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machine = makeMachine();
      const action = "on";
      const defer = $q.defer();
      spyOn(MachinesManager, "performAction").and.returnValue(defer.promise);

      scope.performAction(machine, action);
      expect(machine[`${action}-transition`]).toEqual(true);
    });

    it("executes MachinesManager.performAction correctly", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machine = makeMachine();
      const action = "on";
      const extra = { param: "parameter" };
      const defer = $q.defer();
      spyOn(MachinesManager, "performAction").and.returnValue(defer.promise);

      scope.performAction(machine, action, extra);
      expect(MachinesManager.performAction).toHaveBeenCalledWith(
        machine,
        action,
        extra
      );
    });
  });

  describe("toggleMenu", function() {
    it("opens menu if none are currently open", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.openMenu = "";
      scope.toggleMenu("menu");
      expect(scope.openMenu).toEqual("menu");
    });

    it("closes menu if it is currently open", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.openMenu = "menu";
      scope.toggleMenu("menu");
      expect(scope.openMenu).toEqual("");
    });
  });

  describe("getActionTitle", () => {
    it("returns the correct action title, given an action name", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.table = {
        machineActions: [
          { title: "this action title", name: "this_action" },
          { title: "other action title", name: "other_action" }
        ]
      };

      expect(scope.getActionTitle(scope.table.machineActions[0].name)).toEqual(
        scope.table.machineActions[0].title
      );
    });

    it("returns the default OS and release if action is 'deploy'", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const [defaultOS, otherOS] = [makeOS(), makeOS()];
      const [defaultRelease, otherRelease] = [
        makeRelease(defaultOS),
        makeRelease(otherOS)
      ];

      scope.table = {
        osinfo: {
          default_osystem: defaultOS[0],
          default_release: defaultRelease[0].split("/")[1],
          osystems: [defaultOS, otherOS],
          releases: [defaultRelease, otherRelease]
        },
        machineActions: [{ title: "Deploy...", name: "deploy" }]
      };

      expect(scope.getActionTitle("deploy")).toEqual(
        `Deploy ${defaultOS[1]} ${defaultRelease[1]}...`
      );
    });
  });

  describe("getStatusActions", () => {
    it(`returns the intersection of possible machine actions
            and actions available in the status dropdown`, () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machine = makeMachine();
      scope.statusMenuActions = ["action1", "action2"];
      machine.actions = ["action2", "action3"];

      expect(scope.getStatusActions(machine)).toEqual(["action2"]);
    });
  });

  describe("getActionSentence", () => {
    it("returns generic sentence if no action param present", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();

      expect(scope.getActionSentence()).toEqual("perform action");
    });

    it("returns correctly formatted sentence without machine param", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();

      expect(scope.getActionSentence("on")).toEqual("power on machine");
    });

    it("returns correctly formatted sentence with machine param", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machine = makeMachine();

      expect(scope.getActionSentence("on", machine)).toEqual(
        `power on ${machine.hostname}`
      );
    });
  });

  describe("groupBy", () => {
    it("returns a grouped map accessible by key", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const items = [
        { id: 1, type: "a" },
        { id: 2, type: "a" },
        { id: 3, type: "b" }
      ];
      const grouped = scope.groupBy(items, item => item.type);

      expect(grouped.get("a")).toEqual([
        { id: 1, type: "a" },
        { id: 2, type: "a" }
      ]);
      expect(grouped.get("b")).toEqual([{ id: 3, type: "b" }]);
    });
  });

  describe("updateGroupedMachines", () => {
    it("returns ungrouped machines with label 'none'", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();

      const machines = [makeMachine(), makeMachine()];
      scope.filteredMachines = machines;
      scope.updateGroupedMachines("none");

      expect(scope.groupedMachines).toEqual([{ label: "none", machines }]);
    });

    it("returns machines grouped by status", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();

      // create an array of machines with status_code from 0 -> 22
      const machines = Array(23)
        .fill()
        .map((_, i) => {
          let m = makeMachine();
          m.status_code = i;
          return m;
        });

      scope.filteredMachines = machines;
      scope.updateGroupedMachines("status");

      expect(scope.groupedMachines).toEqual([
        {
          label: "Failed",
          machines: [
            machines[2],
            machines[11],
            machines[13],
            machines[15],
            machines[18],
            machines[20],
            machines[22]
          ]
        },
        { label: "New", machines: [machines[0]] },
        { label: "Commissioning", machines: [machines[1]] },
        { label: "Testing", machines: [machines[21]] },
        { label: "Ready", machines: [machines[4]] },
        { label: "Allocated", machines: [machines[10]] },
        { label: "Deploying", machines: [machines[9]] },
        { label: "Deployed", machines: [machines[6]] },
        {
          label: "Rescue mode",
          machines: [machines[16], machines[17], machines[19]]
        },
        { label: "Releasing", machines: [machines[12], machines[14]] },
        { label: "Broken", machines: [machines[8]] },
        { label: "Other", machines: [machines[7], machines[3], machines[5]] }
      ]);
    });

    it("returns machines grouped by owner", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();

      const machines = [makeMachine(), makeMachine()];
      machines[0].owner = "admin";
      machines[1].owner = "user1";
      scope.filteredMachines = machines;
      scope.updateGroupedMachines("owner");

      expect(scope.groupedMachines).toEqual([
        { label: "admin", machines: [machines[0]] },
        { label: "user1", machines: [machines[1]] }
      ]);
    });
  });

  describe("getGroupSelectedState", () => {
    it("returns true if all machines in a group are selected", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();

      const machines = [makeMachine(), makeMachine()];
      machines[0].status = "New";
      machines[0].$selected = true;
      machines[1].status = "New";
      machines[1].$selected = true;
      scope.table.filteredMachines = machines;
      scope.groupedMachines = [
        { label: "New", machines: [machines[0], machines[1]] }
      ];
      scope.getGroupSelectedState("New");

      expect(scope.getGroupSelectedState("New")).toBe(true);
    });

    it("returns false if not all machines in a group are selected", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();

      const machines = [makeMachine(), makeMachine()];
      machines[0].status = "New";
      machines[0].$selected = true;
      machines[1].status = "New";
      scope.table.filteredMachines = machines;
      scope.groupedMachines = [
        { label: "New", machines: [machines[0], machines[1]] }
      ];
      scope.getGroupSelectedState("New");

      expect(scope.getGroupSelectedState("New")).toBe(false);
    });
  });

  describe("getGroupCountString", () => {
    it(`correctly returns a string of the number of machines in a group,
            and the selected machines in that group`, () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machines = Array.from(Array(6)).map(makeMachine);
      machines[0].$selected = true;
      machines[1].$selected = true;
      machines[2].$selected = true;
      scope.groupedMachines = [
        { label: "New", machines: [machines[0], machines[1]] },
        { label: "Ready", machines: [machines[2], machines[3]] },
        { label: "Failed", machines: [machines[4], machines[5]] }
      ];

      expect(scope.getGroupCountString("New")).toBe("2 machines selected");
      expect(scope.getGroupCountString("Ready")).toBe("2 machines, 1 selected");
      expect(scope.getGroupCountString("Failed")).toBe("2 machines");
    });
  });

  describe("getSpacesTooltipMessage", () => {
    it("correctly returns a list of spaces or empty string", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machines = Array.from(Array(3)).map(makeMachine);
      machines[0].spaces = [];
      machines[1].spaces = ["foobar"];
      machines[2].spaces = ["foobar", "barbaz"];

      expect(scope.getSpacesTooltipMessage(machines[0].spaces)).toBe("");
      expect(scope.getSpacesTooltipMessage(machines[1].spaces)).toBe("");
      expect(scope.getSpacesTooltipMessage(machines[2].spaces)).toBe(`foobar
barbaz`); // Has to be formatted this way for tooltip
    });
  });

  describe("updateFilteredMachines", () => {
    it("sets table filtered machines according to search filter", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const machines = Array.from(Array(4)).map(makeMachine);
      machines[0].$selected = true;
      machines[2].$selected = true;
      scope.table = {
        machines: machines,
        filteredMachines: machines
      };
      scope.search = "in:(Selected)";
      scope.updateFilteredMachines();

      expect(scope.table.filteredMachines).toEqual([machines[0], machines[2]]);
    });
  });

  describe("getArchitectureText", () => {
    it("returns the architecture string as is if no '/generic' string", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      expect(scope.getArchitectureText("i386")).toBe("i386");
    });

    it("removes '/generic' from the architecture string", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      expect(scope.getArchitectureText("i386/generic")).toBe("i386");
    });
  });

  describe("display limits", () => {
    it("returns the default display limit for the group", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();

      scope.groupByLabel = "status";
      const group = {
        label: "Allocated",
        machines: []
      };
      scope.$digest();

      expect(scope.getLimit(group)).toEqual(scope.DISPLAY_LIMIT);
    });

    it("sets the groups display limit to undefined", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();

      scope.groupByLabel = "status";
      const group = {
        label: "New",
        machines: []
      };
      scope.loadAll(group);

      expect(scope.getLimit(group)).toEqual(undefined);
    });
  });
});
