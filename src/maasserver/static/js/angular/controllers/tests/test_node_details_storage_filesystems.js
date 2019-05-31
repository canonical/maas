describe("NodeAddSpecialFilesystemController", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Grab the needed angular pieces.
  var $controller, $rootScope, $parentScope, $scope;
  beforeEach(inject(function($injector) {
    $controller = $injector.get("$controller");
    $rootScope = $injector.get("$rootScope");
    $parentScope = $rootScope.$new();
    $scope = $parentScope.$new();
  }));

  // Load the required dependencies for the
  // NodeAddSpecialFilesystemController.
  var MachinesManager;
  beforeEach(inject(function($injector) {
    MachinesManager = $injector.get("MachinesManager");
  }));

  // Create the node and functions that will be called on the parent.
  var node;
  beforeEach(function() {
    node = {
      system_id: 0
    };
    $parentScope.node = node;
    $parentScope.controllerLoaded = jasmine.createSpy("controllerLoaded");
  });

  // Makes the NodeAddSpecialFilesystemController
  function makeController() {
    // Create the controller.
    var controller = $controller("NodeAddSpecialFilesystemController", {
      $scope: $scope,
      MachinesManager: MachinesManager
    });
    return controller;
  }

  it("sets initial values", function() {
    makeController();

    expect($scope.specialFilesystemTypes).toEqual(["tmpfs", "ramfs"]);
    expect($scope.description).toBeNull();
    expect($scope.filesystem.fstype).toBeNull();
    expect($scope.filesystem.mountPoint).toEqual("");
    expect($scope.filesystem.mountOptions).toEqual("");
    expect($scope.newFilesystem).toEqual({ system_id: 0 });
  });

  it("correctly validates mountpoints", function() {
    makeController();
    var specialFilesystem = $scope.filesystem;

    specialFilesystem.mountPoint = "foo";
    expect(specialFilesystem.isValid()).toBe(false);

    specialFilesystem.mountPoint = "/";
    expect(specialFilesystem.isValid()).toBe(true);

    specialFilesystem.mountPoint = "/foo";
    expect(specialFilesystem.isValid()).toBe(true);
  });

  it("describes a filesystem only if fstype is set", function() {
    makeController();
    var specialFilesystem = $scope.filesystem;

    specialFilesystem.fstype = null;

    expect(specialFilesystem.describe()).not.toBeDefined();
  });

  it("describes a filesystem if mountPoint is set", function() {
    makeController();
    var specialFilesystem = $scope.filesystem;

    specialFilesystem.fstype = "tmpfs";
    specialFilesystem.mountPoint = "/";

    expect(specialFilesystem.describe()).toEqual("tmpfs at /");
  });

  it("describes a percentage size if mountOptions is set", function() {
    makeController();
    var specialFilesystem = $scope.filesystem;

    specialFilesystem.fstype = "tmpfs";
    specialFilesystem.mountPoint = "/";
    specialFilesystem.mountOptions = "size=20%";

    expect(specialFilesystem.describe()).toEqual(
      "tmpfs at / limited to 20% of memory"
    );
  });

  it("describes a size in bytes if mountOptions is set", function() {
    makeController();
    var specialFilesystem = $scope.filesystem;

    specialFilesystem.fstype = "tmpfs";
    specialFilesystem.mountPoint = "/";
    specialFilesystem.mountOptions = "size=5000";

    expect(specialFilesystem.describe()).toEqual(
      "tmpfs at / limited to 5000 bytes"
    );
  });

  it("updates the description when the form is updated", function() {
    makeController();
    $scope.newFilesystem.$maasForm = { getValue: function() {} };
    spyOn($scope.newFilesystem.$maasForm, "getValue").and.returnValue("foo");

    $scope.$digest();

    expect($scope.description).toEqual("foo");
  });
});
