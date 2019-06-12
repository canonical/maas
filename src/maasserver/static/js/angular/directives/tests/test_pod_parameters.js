/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for pod parameters directive.
 */

import MockWebSocket from "testing/websocket";

describe("maasPodParameters", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Get managers before the test.
  var GeneralManager;
  beforeEach(inject(function($injector) {
    GeneralManager = $injector.get("GeneralManager");
    // Mock buildSocket so an actual connection is not made.
    let RegionConnection = $injector.get("RegionConnection");
    let webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
    $scope.obj = {};
  }));

  // Return the compiled directive.
  function compileDirective(slider) {
    var directive;
    var html = [
      "<div>",
      '<maas-obj-form obj="obj" manager="manager" ',
      'table-form="true" save-on-blur="false">',
      '<maas-pod-parameters hide-slider="' + slider + '">',
      "</maas-pod-parameters>",
      "</maas-obj-form>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return angular.element(directive.find("maas-pod-parameters"));
  }

  it("add type field to maasForm", function() {
    compileDirective("true");
    expect($scope.obj.$maasForm.fields.type).toBeDefined();
  });

  describe("with powerTypes", function() {
    var podTypes, powerTypes;
    beforeEach(function() {
      powerTypes = [
        {
          name: "virsh",
          description: "Virsh",
          driver_type: "pod",
          fields: [
            {
              name: "power_address",
              label: "Pod address",
              scope: "bmc"
            },
            {
              name: "power_id",
              label: "Power ID",
              scope: "node"
            }
          ]
        },
        {
          name: "rsd",
          description: "RSD",
          driver_type: "pod",
          fields: [
            {
              name: "rsd_address",
              label: "Pod address",
              scope: "bmc"
            },
            {
              name: "rsd_id",
              label: "Power ID",
              scope: "node"
            }
          ]
        },
        {
          name: "ipmi",
          description: "IPMI",
          driver_type: "power",
          fields: []
        }
      ];
      podTypes = [powerTypes[0], powerTypes[1]];
      GeneralManager._data.power_types.data = powerTypes;
    });

    it("sets podTypes", function() {
      var directive = compileDirective("true");
      var scope = directive.isolateScope();
      podTypes = [powerTypes[0], powerTypes[1]];
      expect(scope.podTypes).toEqual(podTypes);
    });

    it("renders fields when type set", function() {
      compileDirective("false");
      $scope.obj.$maasForm.updateValue("type", "virsh");
      $scope.$digest();

      expect($scope.obj.$maasForm.fields.power_address).toBeDefined();
      expect($scope.obj.$maasForm.fields.power_id).toBeUndefined();
      expect($scope.obj.$maasForm.fields.cpu_over_commit_ratio).toBeDefined();
      expect(
        $scope.obj.$maasForm.fields.memory_over_commit_ratio
      ).toBeDefined();
    });

    it("switches fields when type changed", function() {
      compileDirective("false");
      $scope.obj.$maasForm.updateValue("type", "virsh");
      $scope.$digest();
      $scope.obj.$maasForm.updateValue("type", "rsd");
      $scope.$digest();

      expect($scope.obj.$maasForm.fields.power_address).toBeUndefined();
      expect($scope.obj.$maasForm.fields.power_id).toBeUndefined();
      expect($scope.obj.$maasForm.fields.cpu_over_commit_ratio).toBeUndefined();
      expect(
        $scope.obj.$maasForm.fields.memory_over_commit_ratio
      ).toBeUndefined();
      expect($scope.obj.$maasForm.fields.rsd_address).toBeDefined();
      expect($scope.obj.$maasForm.fields.rsd_id).toBeUndefined();
    });

    it("switches fields back when type changed again", function() {
      compileDirective("false");
      $scope.obj.$maasForm.updateValue("type", "rsd");
      $scope.$digest();
      $scope.obj.$maasForm.updateValue("type", "virsh");
      $scope.$digest();

      expect($scope.obj.$maasForm.fields.power_address).toBeDefined();
      expect($scope.obj.$maasForm.fields.power_id).toBeUndefined();
      expect($scope.obj.$maasForm.fields.cpu_over_commit_ratio).toBeDefined();
      expect(
        $scope.obj.$maasForm.fields.memory_over_commit_ratio
      ).toBeDefined();
      expect($scope.obj.$maasForm.fields.rsd_address).toBeUndefined();
      expect($scope.obj.$maasForm.fields.rsd_id).toBeUndefined();
    });

    it("creates maas-obj-field with type='slider'", function() {
      var directive = compileDirective("false");
      $scope.obj.$maasForm.updateValue("type", "virsh");
      $scope.$digest();

      var sliders = angular.element(
        directive.find('maas-obj-field[type="slider"]')
      );
      expect(sliders.length).toBe(2);
    });

    it("does not create maas-obj-field with type='slider'", function() {
      var directive = compileDirective("true");
      $scope.obj.$maasForm.updateValue("type", "virsh");
      $scope.$digest();

      var sliders = angular.element(
        directive.find('maas-obj-field[type="slider"]')
      );
      expect(sliders.length).toBe(0);
    });
  });
});
