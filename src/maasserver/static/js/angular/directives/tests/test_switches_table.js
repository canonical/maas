/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for switches table directive.
 */

import { makeName } from "testing/utils";

describe("maasSwitchesTable", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Preload the $templateCache with empty contents. We only test the
  // controller of the directive, not the template.
  var $templateCache;
  beforeEach(inject(function($injector) {
    $templateCache = $injector.get("$templateCache");
    $templateCache.put("static/partials/switches-table.html?v=undefined", "");
  }));

  // Load the required managers.
  var SwitchesManager, GeneralManager;
  beforeEach(inject(function($injector) {
    SwitchesManager = $injector.get("SwitchesManager");
    GeneralManager = $injector.get("GeneralManager");
  }));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Makes a switch.
  function makeSwitch() {
    var switch_ = {
      system_id: makeName("system_id"),
      $selected: false
    };
    SwitchesManager._items.push(switch_);
    return switch_;
  }

  // Return the compiled directive with the items from the scope.
  function compileDirective(design) {
    var directive;
    var html = [
      "<div>",
      "<maas-switches-table ",
      'on-listing-change="onListingChange($switches)" ',
      'on-check-all="onCheckAll()" ',
      'on-check="onCheck($switch_)"></maas-switches-table>',
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("maas-switches-table");
  }

  it("sets initial variables", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    expect(scope.table).toEqual({
      column: "fqdn",
      predicate: "fqdn",
      reverse: false,
      allViewableChecked: false,
      switches: SwitchesManager.getItems(),
      filteredSwitches: [],
      osinfo: GeneralManager.getData("osinfo")
    });
    expect(scope.table.switches).toBe(SwitchesManager.getItems());
  });

  describe("updateAllChecked", function() {
    it("sets allViewableChecked to false when no switches", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.table.allViewableChecked = true;
      scope.table.filteredSwitches = [];
      scope.updateAllChecked();
      expect(scope.table.allViewableChecked).toBe(false);
    });

    it("sets allViewableChecked to false when one not selected", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.table.allViewableChecked = true;
      scope.table.filteredSwitches = [
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
      scope.table.filteredSwitches = [
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
    it("unselected all selected switches", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var switch_ = makeSwitch();
      SwitchesManager.selectItem(switch_.system_id);
      scope.table.allViewableChecked = true;
      scope.table.filteredSwitches = [switch_];
      scope.toggleCheckAll();
      expect(switch_.$selected).toBe(false);
      expect(scope.table.allViewableChecked).toBe(false);
    });

    it("selects all unselected switches", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var switch_ = makeSwitch();
      scope.table.allViewableChecked = false;
      scope.table.filteredSwitches = [switch_];
      scope.toggleCheckAll();
      expect(switch_.$selected).toBe(true);
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

  describe("toggleChecked", function() {
    it("selects switch", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var switch_ = makeSwitch();
      scope.table.filteredSwitches = [switch_];
      scope.toggleChecked(switch_);
      expect(switch_.$selected).toBe(true);
      expect(scope.table.allViewableChecked).toBe(true);
    });

    it("unselects switch", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var switch_ = makeSwitch();
      scope.table.filteredSwitches = [switch_];
      SwitchesManager.selectItem(switch_.system_id);
      scope.toggleChecked(switch_);
      expect(switch_.$selected).toBe(false);
      expect(scope.table.allViewableChecked).toBe(false);
    });

    it("calls onCheck", function() {
      $scope.onCheck = jasmine.createSpy("onCheck");
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var switch_ = makeSwitch();
      scope.toggleChecked(switch_);
      expect($scope.onCheck).toHaveBeenCalledWith(switch_);
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
        var switch_ = {
          status_code: i
        };
        var expected = false;
        if (STATUSES.indexOf(i) > -1) {
          expected = true;
        }
        expect(scope.showSpinner(switch_)).toBe(expected);
      }
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
      var switch_ = {
        status: makeName("status")
      };

      expect(scope.getStatusText(switch_)).toBe(switch_.status);
    });

    it("returns status with release title when deploying", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var switch_ = {
        status: "Deploying",
        osystem: "ubuntu",
        distro_series: "xenial"
      };
      scope.table.osinfo = {
        releases: [["ubuntu/xenial", "Ubuntu Xenial"]]
      };
      expect(scope.getStatusText(switch_)).toBe("Deploying Ubuntu Xenial");
    });

    it("returns release title when deployed", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var switch_ = {
        status: "Deployed",
        osystem: "ubuntu",
        distro_series: "xenial"
      };
      scope.table.osinfo = {
        releases: [["ubuntu/xenial", "Ubuntu Xenial"]]
      };
      expect(scope.getStatusText(switch_)).toBe("Ubuntu Xenial");
    });

    it("returns release title without codename when deployed", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var switch_ = {
        status: "Deployed",
        osystem: "ubuntu",
        distro_series: "xenial"
      };
      scope.table.osinfo = {
        releases: [["ubuntu/xenial", 'Ubuntu 16.04 LTS "Xenial Xerus"']]
      };
      expect(scope.getStatusText(switch_)).toBe("Ubuntu 16.04 LTS");
    });
  });

  describe("onListingChange", function() {
    it("called when filteredSwitches changes", function() {
      $scope.onListingChange = jasmine.createSpy("onListingChange");
      var directive = compileDirective();
      var scope = directive.isolateScope();

      var switches = [{}];
      scope.table.filteredSwitches = switches;

      $scope.$digest();
      expect($scope.onListingChange).toHaveBeenCalledWith(switches);
    });
  });
});
