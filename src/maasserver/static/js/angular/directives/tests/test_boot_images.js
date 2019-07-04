/* Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for boot images directive.
 */

import { makeInteger, makeName } from "testing/utils";
import MockWebSocket from "testing/websocket";

describe("maasBootImages", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Preload the $templateCache with empty contents. We only test the
  // controller of the directive, not the template.
  var $q, $templateCache;
  beforeEach(inject(function($injector) {
    $q = $injector.get("$q");
    $templateCache = $injector.get("$templateCache");
    $templateCache.put("static/partials/boot-images.html?v=undefined", "");
  }));

  // Load the required managers.
  var BootResourcesManager, UsersManager, ManagerHelperService;
  beforeEach(inject(function($injector) {
    BootResourcesManager = $injector.get("BootResourcesManager");
    UsersManager = $injector.get("UsersManager");
    ManagerHelperService = $injector.get("ManagerHelperService");
    // Mock buildSocket so an actual connection is not made.
    let RegionConnection = $injector.get("RegionConnection");
    let webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective(design) {
    if (angular.isUndefined(design)) {
      design = "";
    }
    var directive;
    var html = [
      "<div>",
      '<maas-boot-images design="' + design + '"></maas-boot-images>',
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("maas-boot-images");
  }

  it("sets initial variables", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    expect(scope.loading).toBe(true);
    expect(scope.saving).toBe(false);
    expect(scope.design).toBe("page");
    expect(scope.bootResources).toBe(BootResourcesManager.getData());
    expect(scope.ubuntuImages).toEqual([]);
    expect(scope.source).toEqual({
      isNew: false,
      tooMany: false,
      showingAdvanced: false,
      connecting: false,
      errorMessage: "",
      source_type: "maas.io",
      url: "",
      keyring_filename: "",
      keyring_data: "",
      releases: [],
      arches: [],
      selections: {
        changed: false,
        releases: [],
        arches: []
      }
    });
    expect(scope.otherImages).toEqual([]);
    expect(scope.other).toEqual({
      changed: false,
      images: []
    });
    expect(scope.generatedImages).toEqual([]);
    expect(scope.customImages).toEqual([]);
    expect(scope.ubuntuDeleteId).toBeNull();
    expect(scope.removingImage).toBeNull();
  });

  it("clears loading once polling and user manager loaded", function() {
    var pollingDefer = $q.defer();
    spyOn(BootResourcesManager, "startPolling").and.returnValue(
      pollingDefer.promise
    );
    var managerDefer = $q.defer();
    spyOn(ManagerHelperService, "loadManager").and.returnValue(
      managerDefer.promise
    );

    var directive = compileDirective();
    var scope = directive.isolateScope();

    pollingDefer.resolve();
    $scope.$digest();
    managerDefer.resolve();
    $scope.$digest();
    expect(scope.loading).toBe(false);
  });

  it("calls updateSource when ubuntu changes", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    spyOn(scope, "updateSource");
    scope.bootResources.ubuntu = {};
    $scope.$digest();

    expect(scope.updateSource).toHaveBeenCalled();
  });

  it("calls all regenerates when resources changes", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    spyOn(scope, "regenerateUbuntuImages");
    spyOn(scope, "regenerateUbuntuCoreImages");
    spyOn(scope, "regenerateOtherImages");
    spyOn(scope, "regenerateGeneratedImages");
    spyOn(scope, "regenerateCustomImages");
    scope.bootResources.resources = [];
    $scope.$digest();

    expect(scope.regenerateUbuntuImages).toHaveBeenCalled();
    expect(scope.regenerateUbuntuCoreImages).toHaveBeenCalled();
    expect(scope.regenerateOtherImages).toHaveBeenCalled();
    expect(scope.regenerateGeneratedImages).toHaveBeenCalled();
    expect(scope.regenerateCustomImages).toHaveBeenCalled();
  });

  it("sets ubuntu_core.images when ubuntu_core change", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    spyOn(scope, "regenerateUbuntuCoreImages");
    var sentinel = [];
    scope.bootResources.ubuntu_core_images = sentinel;
    $scope.$digest();

    expect(scope.ubuntu_core.images).toBe(sentinel);
    expect(scope.regenerateUbuntuCoreImages).toHaveBeenCalled();
  });

  it("doesnt sets ubuntu_core.images when ubuntu_core changed", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    spyOn(scope, "regenerateUbuntuCoreImages");
    var sentinel = [];
    scope.bootResources.ubuntu_core_images = sentinel;
    scope.ubuntu_core.changed = true;
    $scope.$digest();

    expect(scope.ubuntu_core.images).not.toBe(sentinel);
    expect(scope.regenerateUbuntuCoreImages).toHaveBeenCalled();
  });

  it("sets other.images when other_images change", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    spyOn(scope, "regenerateOtherImages");
    var sentinel = [];
    scope.bootResources.other_images = sentinel;
    $scope.$digest();

    expect(scope.other.images).toBe(sentinel);
    expect(scope.regenerateOtherImages).toHaveBeenCalled();
  });

  it("doesnt sets other.images when other changed", function() {
    var directive = compileDirective();
    var scope = directive.isolateScope();
    spyOn(scope, "regenerateOtherImages");
    var sentinel = [];
    scope.bootResources.other_images = sentinel;
    scope.other.changed = true;
    $scope.$digest();

    expect(scope.other.images).not.toBe(sentinel);
    expect(scope.regenerateOtherImages).toHaveBeenCalled();
  });

  it("stops polling when scope is destroyed", function() {
    var directive = compileDirective();
    spyOn(BootResourcesManager, "stopPolling");
    directive.scope().$destroy();
    expect(BootResourcesManager.stopPolling).toHaveBeenCalled();
  });

  describe("isSuperUser", function() {
    it("returns UsersManager.isSuperUser", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();

      var sentinel = {};
      spyOn(UsersManager, "isSuperUser").and.returnValue(sentinel);
      expect(scope.isSuperUser()).toBe(sentinel);
    });
  });

  describe("getTitleIcon", function() {
    it("returns error when no resources", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      BootResourcesManager._data.resources = [];
      expect(scope.getTitleIcon()).toBe("p-icon--success-muted");
    });

    it("returns success when resources", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      BootResourcesManager._data.resources = [{}];
      expect(scope.getTitleIcon()).toBe("p-icon--success");
    });
  });

  describe("showMirrorPath", function() {
    it("returns true when custom", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.source_type = "custom";
      expect(scope.showMirrorPath()).toBe(true);
    });

    it("returns false when maas.io", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.source_type = "maas.io";
      expect(scope.showMirrorPath()).toBe(false);
    });
  });

  describe("isShowingAdvancedOptions", function() {
    it("returns showingAdvanced", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var sentinel = {};
      scope.source.showingAdvanced = sentinel;
      expect(scope.isShowingAdvancedOptions()).toBe(sentinel);
    });
  });

  describe("toggleAdvancedOptions", function() {
    it("inverts showingAdvanced", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.showingAdvanced = false;
      scope.toggleAdvancedOptions();
      expect(scope.source.showingAdvanced).toBe(true);
      scope.toggleAdvancedOptions();
      expect(scope.source.showingAdvanced).toBe(false);
    });
  });

  describe("bothKeyringOptionsSet", function() {
    it("returns false if neither set", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      expect(scope.bothKeyringOptionsSet()).toBe(false);
    });

    it("returns false if keyring_filename set", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.keyring_filename = makeName("file");
      expect(scope.bothKeyringOptionsSet()).toBe(false);
    });

    it("returns false if keyring_data set", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.keyring_data = makeName("data");
      expect(scope.bothKeyringOptionsSet()).toBe(false);
    });

    it("returns true if both set set", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.keyring_filename = makeName("file");
      scope.source.keyring_data = makeName("data");
      expect(scope.bothKeyringOptionsSet()).toBe(true);
    });
  });

  describe("showConnectButton", function() {
    it("returns isNew", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var sentinel = {};
      scope.source.isNew = sentinel;
      expect(scope.showConnectButton()).toBe(sentinel);
    });
  });

  describe("sourceChanged", function() {
    it("sets isNew if no sources", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources = {
        resources: [],
        ubuntu: {
          sources: []
        }
      };
      spyOn(scope, "connect");
      scope.sourceChanged();
      expect(scope.source.isNew).toBe(true);
    });

    it("calls connect when no sources", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources = {
        resources: [],
        ubuntu: {
          sources: []
        }
      };
      spyOn(scope, "connect");
      scope.sourceChanged();
      expect(scope.connect).toHaveBeenCalled();
    });

    it("calls connect when no sources", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources = {
        resources: [],
        ubuntu: {
          sources: []
        }
      };
      spyOn(scope, "connect");
      scope.sourceChanged();
      expect(scope.connect).toHaveBeenCalled();
    });

    it("calls updateSource and regenerateUbuntuImages", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources = {
        resources: [],
        ubuntu: {
          sources: []
        }
      };
      spyOn(scope, "connect");
      spyOn(scope, "updateSource");
      spyOn(scope, "regenerateUbuntuImages");
      scope.sourceChanged();
      expect(scope.updateSource).toHaveBeenCalled();
      expect(scope.regenerateUbuntuImages).toHaveBeenCalled();
    });

    it("changing to maas.io clears options and selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources = {
        resources: [],
        ubuntu: {
          sources: [
            {
              source_type: "custom"
            }
          ]
        }
      };
      scope.source.isNew = false;
      scope.source.source_type = "maas.io";
      scope.source.releases = [{}, {}];
      scope.source.arches = [{}, {}];
      scope.source.selections = {
        changed: true,
        releases: [{}],
        arches: [{}]
      };
      spyOn(scope, "connect");
      scope.sourceChanged();
      expect(scope.source.releases).toEqual([]);
      expect(scope.source.arches).toEqual([]);
      expect(scope.source.selections).toEqual({
        changed: false,
        releases: [],
        arches: []
      });
    });

    it("changing to custom clears options and selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources = {
        resources: [],
        ubuntu: {
          sources: [
            {
              source_type: "maas.io"
            }
          ]
        }
      };
      scope.source.isNew = false;
      scope.source.source_type = "custom";
      scope.source.releases = [{}, {}];
      scope.source.arches = [{}, {}];
      scope.source.selections = {
        changed: true,
        releases: [{}],
        arches: [{}]
      };
      spyOn(scope, "connect");
      scope.sourceChanged();
      expect(scope.source.releases).toEqual([]);
      expect(scope.source.arches).toEqual([]);
      expect(scope.source.selections).toEqual({
        changed: false,
        releases: [],
        arches: []
      });
    });

    it("changing to custom url clears options and selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources = {
        resources: [],
        ubuntu: {
          sources: [
            {
              source_type: "custom",
              url: ""
            }
          ]
        }
      };
      scope.source.isNew = false;
      scope.source.source_type = "custom";
      scope.source.url = makeName("url");
      scope.source.releases = [{}, {}];
      scope.source.arches = [{}, {}];
      scope.source.selections = {
        changed: true,
        releases: [{}],
        arches: [{}]
      };
      spyOn(scope, "connect");
      scope.sourceChanged();
      expect(scope.source.releases).toEqual([]);
      expect(scope.source.arches).toEqual([]);
      expect(scope.source.selections).toEqual({
        changed: false,
        releases: [],
        arches: []
      });
    });
  });

  describe("isConnectButtonDisabled", function() {
    it("never disabled when maas.io", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.source_type = "maas.io";
      expect(scope.isConnectButtonDisabled()).toBe(false);
    });

    it("disabled when custom and both keyrings are set", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.source_type = "custom";
      spyOn(scope, "bothKeyringOptionsSet").and.returnValue(true);
      expect(scope.isConnectButtonDisabled()).toBe(true);
    });

    it("disabled when custom and no url", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.source_type = "custom";
      scope.source.url = "";
      expect(scope.isConnectButtonDisabled()).toBe(true);
    });

    it("disabled when custom connecting", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.source_type = "custom";
      scope.source.url = makeName("url");
      scope.source.connecting = true;
      expect(scope.isConnectButtonDisabled()).toBe(true);
    });

    it("enabled when custom and not connecting", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.source_type = "custom";
      scope.source.url = makeName("url");
      scope.source.connecting = false;
      expect(scope.isConnectButtonDisabled()).toBe(false);
    });
  });

  describe("getSourceParams", function() {
    it("maas.io only returns source_type", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.source_type = "maas.io";
      expect(scope.getSourceParams()).toEqual({
        source_type: "maas.io"
      });
    });

    it("custom returns all fields", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.source_type = "custom";
      scope.source.url = makeName("url");
      scope.source.keyring_filename = makeName("keyring_filename");
      scope.source.keyring_data = makeName("keyring_data");
      expect(scope.getSourceParams()).toEqual({
        source_type: "custom",
        url: scope.source.url,
        keyring_filename: scope.source.keyring_filename,
        keyring_data: scope.source.keyring_data
      });
    });
  });

  describe("selectDefaults", function() {
    it("selects bionic and amd64", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var bionic = {
        name: "bionic"
      };
      var amd64 = {
        name: "amd64"
      };
      scope.source.releases = [bionic];
      scope.source.arches = [amd64];
      scope.selectDefaults();

      expect(scope.source.selections.releases).toEqual([bionic]);
      expect(scope.source.selections.arches).toEqual([amd64]);
    });
  });

  describe("connect", function() {
    it("does nothing if disabled", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "isConnectButtonDisabled").and.returnValue(true);
      spyOn(BootResourcesManager, "fetch");
      scope.connect();
      expect(BootResourcesManager.fetch).not.toHaveBeenCalled();
    });

    it("toggles connecting and sets options and defaults", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "isConnectButtonDisabled").and.returnValue(false);

      // Mock the fetch call.
      var defer = $q.defer();
      spyOn(BootResourcesManager, "fetch").and.returnValue(defer.promise);
      spyOn(scope, "regenerateUbuntuImages");
      scope.connect();
      expect(scope.source.connecting).toBe(true);

      // Call connect and fake the resolve with mock data.
      spyOn(scope, "selectDefaults");
      var release = makeName("release");
      var arch = makeName("arch");
      var data = angular.toJson({
        releases: [
          {
            name: release
          }
        ],
        arches: [
          {
            name: arch
          }
        ]
      });
      defer.resolve(data);
      $scope.$digest();

      expect(scope.source.connecting).toBe(false);
      expect(scope.source.releases).toEqual([
        {
          name: release
        }
      ]);
      expect(scope.source.arches).toEqual([
        {
          name: arch
        }
      ]);
      expect(scope.selectDefaults).toHaveBeenCalled();
      expect(scope.regenerateUbuntuImages).toHaveBeenCalled();
    });

    it("toggles connecting and sets error", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "isConnectButtonDisabled").and.returnValue(false);

      // Mock the fetch call.
      var defer = $q.defer();
      spyOn(BootResourcesManager, "fetch").and.returnValue(defer.promise);
      spyOn(scope, "regenerateUbuntuImages");
      scope.connect();
      expect(scope.source.connecting).toBe(true);

      // Call connect and fake the reject.
      var error = makeName("error");
      defer.reject(error);
      $scope.$digest();

      expect(scope.source.connecting).toBe(false);
      expect(scope.source.errorMessage).toBe(error);
    });
  });

  describe("showConnectBlock", function() {
    it("true if tooMany sources", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.tooMany = true;
      expect(scope.showConnectBlock()).toBe(true);
    });

    it("true if new and not showing selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.isNew = true;
      spyOn(scope, "showSelections").and.returnValue(false);
      expect(scope.showConnectBlock()).toBe(true);
    });

    it("false if new and showing selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.isNew = true;
      spyOn(scope, "showSelections").and.returnValue(true);
      expect(scope.showConnectBlock()).toBe(false);
    });

    it("false if not new", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.isNew = false;
      spyOn(scope, "showSelections").and.returnValue(false);
      expect(scope.showConnectBlock()).toBe(false);
    });
  });

  describe("showSelections", function() {
    it("true releases and arches exist", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.releases = [{}];
      scope.source.arches = [{}];
      expect(scope.showSelections()).toBe(true);
    });

    it("false if only releases", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.releases = [{}];
      scope.source.arches = [];
      expect(scope.showSelections()).toBe(false);
    });

    it("false if only arches", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.source.releases = [];
      scope.source.arches = [{}];
      expect(scope.showSelections()).toBe(false);
    });
  });

  describe("getUbuntuLTSReleases", function() {
    it("filters bootResources to LTS", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var lts = {
        title: "16.04 LTS",
        deleted: false
      };
      var nonLTS = {
        title: "16.10",
        deleted: false
      };
      scope.bootResources = {
        ubuntu: {
          releases: [lts, nonLTS]
        }
      };
      expect(scope.getUbuntuLTSReleases()).toEqual([lts]);
    });

    it("filters deleted releases", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var lts = {
        title: "16.04 LTS",
        deleted: false
      };
      var deletedLTS = {
        title: "12.04 LTS",
        deleted: true
      };
      scope.bootResources = {
        ubuntu: {
          releases: [lts, deletedLTS]
        }
      };
      expect(scope.getUbuntuLTSReleases()).toEqual([lts]);
    });

    it("filters new sources to LTS", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var lts = {
        title: "16.04 LTS",
        deleted: false
      };
      var nonLTS = {
        title: "16.10",
        deleted: false
      };
      scope.bootResources = {
        ubuntu: {
          releases: []
        }
      };
      scope.source.isNew = true;
      scope.source.releases = [lts, nonLTS];
      expect(scope.getUbuntuLTSReleases()).toEqual([lts]);
    });
  });

  describe("getUbuntuNonLTSReleases", function() {
    it("filters bootResources to non-LTS", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var lts = {
        title: "16.04 LTS",
        deleted: false
      };
      var nonLTS = {
        title: "16.10",
        deleted: false
      };
      scope.bootResources = {
        ubuntu: {
          releases: [lts, nonLTS]
        }
      };
      expect(scope.getUbuntuNonLTSReleases()).toEqual([nonLTS]);
    });

    it("filters deleted releases", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var nonLTS = {
        title: "16.10",
        deleted: false
      };
      var deleted = {
        title: "15.04",
        deleted: true
      };
      scope.bootResources = {
        ubuntu: {
          releases: [nonLTS, deleted]
        }
      };
      expect(scope.getUbuntuNonLTSReleases()).toEqual([nonLTS]);
    });

    it("filters new sources to non-LTS", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var lts = {
        title: "16.04 LTS",
        deleted: false
      };
      var nonLTS = {
        title: "16.10",
        deleted: false
      };
      scope.bootResources = {
        ubuntu: {
          releases: []
        }
      };
      scope.source.isNew = true;
      scope.source.releases = [lts, nonLTS];
      expect(scope.getUbuntuNonLTSReleases()).toEqual([nonLTS]);
    });
  });

  describe("getArchitectures", function() {
    it("returns bootResources arches", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var arch1 = {
        deleted: false
      };
      var arch2 = {
        deleted: false
      };
      scope.bootResources = {
        ubuntu: {
          arches: [arch1, arch2]
        }
      };
      expect(scope.getArchitectures()).toEqual([arch1, arch2]);
    });

    it("filters deleted arches", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var arch1 = {
        deleted: false
      };
      var arch2 = {
        deleted: true
      };
      scope.bootResources = {
        ubuntu: {
          arches: [arch1, arch2]
        }
      };
      expect(scope.getArchitectures()).toEqual([arch1]);
    });

    it("returns new sources arches", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var arch1 = {
        deleted: false
      };
      var arch2 = {
        deleted: false
      };
      scope.bootResources = {
        ubuntu: {
          arches: []
        }
      };
      scope.source.isNew = true;
      scope.source.arches = [arch1, arch2];
      expect(scope.getArchitectures()).toEqual([arch1, arch2]);
    });
  });

  describe("isSelected", function() {
    it("returns true if in release selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var obj = {};
      scope.source.selections.releases = [obj];
      expect(scope.isSelected("releases", obj)).toBe(true);
    });

    it("returns false if not in release selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var obj = {};
      scope.source.selections.releases = [obj];
      expect(scope.isSelected("releases", {})).toBe(false);
    });

    it("returns true if in arch selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var obj = {};
      scope.source.selections.arches = [obj];
      expect(scope.isSelected("arches", obj)).toBe(true);
    });

    it("returns false if not in arch selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var obj = {};
      scope.source.selections.arches = [obj];
      expect(scope.isSelected("arches", {})).toBe(false);
    });
  });

  describe("toggleSelection", function() {
    it("selects the obj for releases", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var obj = {};
      spyOn(scope, "regenerateUbuntuImages");
      scope.toggleSelection("releases", obj);
      expect(scope.source.selections.changed).toBe(true);
      expect(scope.source.selections.releases).toEqual([obj]);
      expect(scope.regenerateUbuntuImages).toHaveBeenCalled();
    });

    it("deselects the obj for releases", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var obj = {};
      scope.source.selections.releases = [obj];
      spyOn(scope, "regenerateUbuntuImages");
      scope.toggleSelection("releases", obj);
      expect(scope.source.selections.changed).toBe(true);
      expect(scope.source.selections.releases).toEqual([]);
      expect(scope.regenerateUbuntuImages).toHaveBeenCalled();
    });

    it("selects the obj for arches", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var obj = {};
      spyOn(scope, "regenerateUbuntuImages");
      scope.toggleSelection("arches", obj);
      expect(scope.source.selections.changed).toBe(true);
      expect(scope.source.selections.arches).toEqual([obj]);
      expect(scope.regenerateUbuntuImages).toHaveBeenCalled();
    });

    it("deselects the obj for arches", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var obj = {};
      scope.source.selections.arches = [obj];
      spyOn(scope, "regenerateUbuntuImages");
      scope.toggleSelection("arches", obj);
      expect(scope.source.selections.changed).toBe(true);
      expect(scope.source.selections.arches).toEqual([]);
      expect(scope.regenerateUbuntuImages).toHaveBeenCalled();
    });
  });

  describe("showImagesTable", function() {
    it("returns true if ubuntuImages exist", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.ubuntuImages = [{}];
      expect(scope.showImagesTable()).toBe(true);
    });

    it("returns true source has arches and releases", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.ubuntuImages = [];
      scope.source.arches = [{}];
      scope.source.releases = [{}];
      expect(scope.showImagesTable()).toBe(true);
    });

    it("returns false no images and no source info", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.ubuntuImages = [];
      scope.source.arches = [];
      scope.source.releases = [];
      expect(scope.showImagesTable()).toBe(false);
    });
  });

  describe("regenerateUbuntuImages", function() {
    it("builds images based on selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources.resources = [];
      var release = {
        name: makeName("release"),
        title: makeName("releaseTitle")
      };
      var arch = {
        name: makeName("arch"),
        title: makeName("archTitle")
      };
      scope.source.selections.releases = [release];
      scope.source.selections.arches = [arch];
      scope.regenerateUbuntuImages();
      expect(scope.ubuntuImages).toEqual([
        {
          icon: "p-icon--status-queued",
          title: release.title,
          arch: arch.title,
          size: "-",
          status: "Selected for download",
          beingDeleted: false,
          name: release.name
        }
      ]);
    });

    it("builds images based on selection and resource", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var release = {
        name: makeName("release"),
        title: makeName("releaseTitle")
      };
      var arch = {
        name: makeName("arch"),
        title: makeName("archTitle")
      };
      var icon = makeName("icon");
      var size = makeName("size");
      var status = makeName("status");
      var resourceId = makeInteger(0, 100);
      scope.bootResources.resources = [
        {
          id: resourceId,
          rtype: 0,
          name: "ubuntu/" + release.name,
          arch: arch.name,
          icon: icon,
          size: size,
          status: status,
          downloading: true
        }
      ];
      scope.source.selections.releases = [release];
      scope.source.selections.arches = [arch];
      scope.regenerateUbuntuImages();
      expect(scope.ubuntuImages).toEqual([
        {
          icon: "p-icon--status-" + icon + " u-animation--pulse",
          title: release.title,
          arch: arch.title,
          size: size,
          status: status,
          beingDeleted: false,
          name: release.name,
          resourceId: resourceId
        }
      ]);
    });

    it("marks resource as being deleted", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var release = {
        name: makeName("release"),
        title: makeName("releaseTitle")
      };
      var arch = {
        name: makeName("arch"),
        title: makeName("archTitle")
      };
      var icon = makeName("icon");
      var size = makeName("size");
      var status = makeName("status");
      scope.bootResources.resources = [
        {
          rtype: 0,
          name: "ubuntu/" + release.name,
          title: release.title,
          arch: arch.name,
          icon: icon,
          size: size,
          status: status,
          downloading: true
        }
      ];
      scope.source.selections.releases = [];
      scope.source.selections.arches = [];
      scope.regenerateUbuntuImages();
      expect(scope.ubuntuImages).toEqual([
        {
          icon: "p-icon--status-failed",
          title: release.title,
          arch: arch.name,
          size: size,
          status: "Will be deleted",
          beingDeleted: true,
          name: release.name
        }
      ]);
    });
  });

  describe("regenerateUbuntuCoreImages", function() {
    it("builds images based on selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources.resources = [];
      var release = makeName("release");
      var arch = makeName("arch");
      var name = "ubuntu-core/" + arch + "/generic/" + release;
      var image = {
        name: name,
        title: makeName("title"),
        checked: true
      };
      scope.ubuntu_core.images = [image];
      scope.regenerateUbuntuCoreImages();
      expect(scope.ubuntuCoreImages).toEqual([
        {
          icon: "p-icon--status-queued",
          title: image.title,
          arch: arch,
          size: "-",
          status: "Selected for download",
          beingDeleted: false
        }
      ]);
    });

    it("builds images based on selection and resource", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var release = makeName("release");
      var arch = makeName("arch");
      var name = "ubuntu-core/" + arch + "/generic/" + release;
      var image = {
        name: name,
        title: makeName("title"),
        checked: true
      };
      var icon = makeName("icon");
      var size = makeName("size");
      var status = makeName("status");
      scope.bootResources.resources = [
        {
          rtype: 0,
          name: "ubuntu-core/" + release,
          arch: arch,
          icon: icon,
          size: size,
          status: status,
          downloading: true
        }
      ];
      scope.ubuntu_core.images = [image];
      scope.regenerateUbuntuCoreImages();
      expect(scope.ubuntuCoreImages).toEqual([
        {
          icon: "p-icon--status-" + icon + " u-animation--pulse",
          title: image.title,
          arch: arch,
          size: size,
          status: status,
          beingDeleted: false
        }
      ]);
    });

    it("marks resource as being deleted", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var release = makeName("release");
      var arch = makeName("arch");
      var name = "ubuntu-core/" + arch + "/generic/" + release;
      var image = {
        name: name,
        title: makeName("title"),
        checked: false
      };
      var icon = makeName("icon");
      var size = makeName("size");
      var status = makeName("status");
      scope.bootResources.resources = [
        {
          rtype: 0,
          name: "ubuntu-core/" + release,
          title: image.title,
          arch: arch,
          icon: icon,
          size: size,
          status: status,
          downloading: true
        }
      ];
      scope.ubuntu_core.images = [image];
      scope.regenerateUbuntuCoreImages();
      expect(scope.ubuntuCoreImages).toEqual([
        {
          icon: "p-icon--status-failed",
          title: image.title,
          arch: arch,
          size: size,
          status: "Will be deleted",
          beingDeleted: true
        }
      ]);
    });
  });

  describe("regenerateOtherImages", function() {
    it("builds images based on selections", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources.resources = [];
      var os = makeName("os");
      var release = makeName("release");
      var arch = makeName("arch");
      var name = os + "/" + arch + "/generic/" + release;
      var image = {
        name: name,
        title: makeName("title"),
        checked: true
      };
      scope.other.images = [image];
      scope.regenerateOtherImages();
      expect(scope.otherImages).toEqual([
        {
          icon: "p-icon--status-queued",
          title: image.title,
          arch: arch,
          size: "-",
          status: "Selected for download",
          beingDeleted: false
        }
      ]);
    });

    it("builds images based on selection and resource", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var os = makeName("os");
      var release = makeName("release");
      var arch = makeName("arch");
      var name = os + "/" + arch + "/generic/" + release;
      var image = {
        name: name,
        title: makeName("title"),
        checked: true
      };
      var icon = makeName("icon");
      var size = makeName("size");
      var status = makeName("status");
      scope.bootResources.resources = [
        {
          rtype: 0,
          name: os + "/" + release,
          arch: arch,
          icon: icon,
          size: size,
          status: status,
          downloading: true
        }
      ];
      scope.other.images = [image];
      scope.regenerateOtherImages();
      expect(scope.otherImages).toEqual([
        {
          icon: "p-icon--status-" + icon + " u-animation--pulse",
          title: image.title,
          arch: arch,
          size: size,
          status: status,
          beingDeleted: false
        }
      ]);
    });

    it("marks resource as being deleted", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var os = makeName("os");
      var release = makeName("release");
      var arch = makeName("arch");
      var name = os + "/" + arch + "/generic/" + release;
      var image = {
        name: name,
        title: makeName("title"),
        checked: false
      };
      var icon = makeName("icon");
      var size = makeName("size");
      var status = makeName("status");
      scope.bootResources.resources = [
        {
          rtype: 0,
          name: os + "/" + release,
          title: image.title,
          arch: arch,
          icon: icon,
          size: size,
          status: status,
          downloading: true
        }
      ];
      scope.other.images = [image];
      scope.regenerateOtherImages();
      expect(scope.otherImages).toEqual([
        {
          icon: "p-icon--status-failed",
          title: image.title,
          arch: arch,
          size: size,
          status: "Will be deleted",
          beingDeleted: true
        }
      ]);
    });
  });

  describe("regenerateGeneratedImages", function() {
    it("builds images based on resource", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var icon = makeName("icon");
      var title = makeName("title");
      var arch = makeName("arch");
      var size = makeName("size");
      var status = makeName("status");
      scope.bootResources.resources = [
        {
          id: 3,
          rtype: 1,
          icon: icon,
          title: title,
          arch: arch,
          size: size,
          status: status,
          downloading: true
        }
      ];
      scope.regenerateGeneratedImages();
      expect(scope.generatedImages).toEqual([
        {
          icon: "p-icon--status-" + icon + " u-animation--pulse",
          title: title,
          arch: arch,
          image_id: 3,
          size: size,
          status: status
        }
      ]);
    });
  });

  describe("regenerateCustomImages", function() {
    it("builds images based on resource", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var icon = makeName("icon");
      var title = makeName("title");
      var arch = makeName("arch");
      var size = makeName("size");
      var status = makeName("status");
      scope.bootResources.resources = [
        {
          rtype: 2,
          id: 3,
          icon: icon,
          title: title,
          arch: arch,
          size: size,
          status: status,
          downloading: true
        }
      ];
      scope.regenerateCustomImages();
      expect(scope.customImages).toEqual([
        {
          icon: "p-icon--status-" + icon + " u-animation--pulse",
          title: title,
          arch: arch,
          image_id: 3,
          size: size,
          status: status
        }
      ]);
    });
  });

  describe("isShowingDeleteConfirm", function() {
    it("returns false when not deleting", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = { image_id: 3 };
      expect(scope.isShowingDeleteConfirm(image)).toBe(false);
    });

    it("returns true when deleting this image", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image1 = { image_id: 3 };
      scope.removingImage = image1;
      expect(scope.isShowingDeleteConfirm(image1)).toBe(true);
    });

    it("returns false when deleting other image", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image1 = { image_id: 3 };
      var image2 = { image_id: 7 };
      scope.removingImage = image1;
      expect(scope.isShowingDeleteConfirm(image2)).toBe(false);
    });
  });

  describe("quickRemove", function() {
    it("sets removingImage", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = { image_id: 3 };
      scope.quickRemove(image);
      expect(scope.removingImage).toBe(image);
    });
  });

  describe("cancelRemove", function() {
    it("clears removingImage", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = { image_id: 3 };
      scope.removingImage = image;
      scope.cancelRemove();
      expect(scope.removingImage).toBe(null);
    });
  });

  describe("confirmRemove", function() {
    it("calls delete_image if given removingImage", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image1 = { image_id: 3 };
      scope.removingImage = image1;
      spyOn(BootResourcesManager, "deleteImage");
      scope.confirmRemove(image1);
      expect(scope.removingImage).toBe(null);
      expect(BootResourcesManager.deleteImage).toHaveBeenCalledWith({
        id: image1.image_id
      });
    });

    it("does not call delete_image if given other image", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image1 = { image_id: 3 };
      var image2 = { image_id: 7 };
      scope.removingImage = image1;
      spyOn(BootResourcesManager, "deleteImage");
      scope.confirmRemove(image2);
      expect(scope.removingImage).toBe(null);
      expect(BootResourcesManager.deleteImage).not.toHaveBeenCalled();
    });
  });

  describe("ltsIsSelected", function() {
    it("returns true if LTS is selected", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = {
        title: "16.04 LTS",
        beingDeleted: false
      };
      scope.ubuntuImages = [image];
      expect(scope.ltsIsSelected()).toBe(true);
    });

    it("returns true if 14 series LTS is selected", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = {
        title: "14.04 LTS",
        beingDeleted: false
      };
      scope.ubuntuImages = [image];
      expect(scope.ltsIsSelected()).toBe(true);
    });

    it("returns false if LTS is being deleted", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = {
        title: "16.04 LTS",
        beingDeleted: true
      };
      scope.ubuntuImages = [image];
      expect(scope.ltsIsSelected()).toBe(false);
    });

    it("returns false if less than 14 series", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = {
        title: "12.04 LTS",
        beingDeleted: false
      };
      scope.ubuntuImages = [image];
      expect(scope.ltsIsSelected()).toBe(false);
    });
  });

  describe("commissioningSeriesSelected", function() {
    it("returns true when selected", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources.ubuntu = {
        commissioning_series: makeName("series")
      };
      scope.ubuntuImages = [
        {
          name: scope.bootResources.ubuntu.commissioning_series,
          beingDeleted: false
        }
      ];
      expect(scope.commissioningSeriesSelected()).toBe(true);
    });

    it("returns false when being deleted", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources.ubuntu = {
        commissioning_series: makeName("series")
      };
      scope.ubuntuImages = [
        {
          name: scope.bootResources.ubuntu.commissioning_series,
          beingDeleted: true
        }
      ];
      expect(scope.commissioningSeriesSelected()).toBe(false);
    });

    it("returns false when unselected", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources.ubuntu = {
        commissioning_series: makeName("series")
      };
      expect(scope.commissioningSeriesSelected()).toBe(false);
    });
  });

  describe("showStopImportButton", function() {
    it("returns region_import_running", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var sentinel = {};
      scope.bootResources.region_import_running = sentinel;
      expect(scope.showStopImportButton()).toBe(sentinel);
    });
  });

  describe("showSaveSelection", function() {
    it("returns showImagesTable", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var sentinel = {};
      spyOn(scope, "showImagesTable").and.returnValue(sentinel);
      expect(scope.showSaveSelection()).toBe(sentinel);
    });
  });

  describe("canSaveSelection", function() {
    it("returns false if deleting commissioning series", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources.ubuntu = {
        commissioning_series: makeName("series")
      };
      scope.ubuntuImages = [
        {
          beingDeleted: true,
          name: scope.bootResources.ubuntu.commissioning_series
        }
      ];
      expect(scope.canSaveSelection()).toBe(false);
    });

    it("returns true if deleting one commissioning series", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.saving = false;
      spyOn(scope, "ltsIsSelected").and.returnValue(true);
      scope.bootResources.ubuntu = {
        commissioning_series: makeName("series")
      };
      scope.ubuntuImages = [
        {
          beingDeleted: true,
          name: scope.bootResources.ubuntu.commissioning_series,
          arch: makeName("arch")
        },
        {
          beingDeleted: false,
          name: scope.bootResources.ubuntu.commissioning_series,
          arch: makeName("arch")
        }
      ];
      expect(scope.canSaveSelection()).toBe(true);
    });

    it("returns false if saving", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.saving = true;
      spyOn(scope, "ltsIsSelected").and.returnValue(true);
      expect(scope.canSaveSelection()).toBe(false);
    });

    it("returns false if stopping", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.saving = false;
      scope.stopping = true;
      spyOn(scope, "ltsIsSelected").and.returnValue(true);
      expect(scope.canSaveSelection()).toBe(false);
    });

    it("returns false if not lts selected", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.saving = false;
      spyOn(scope, "ltsIsSelected").and.returnValue(false);
      expect(scope.canSaveSelection()).toBe(false);
    });

    it("returns true if lts selected and not saving", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.saving = false;
      spyOn(scope, "ltsIsSelected").and.returnValue(true);
      expect(scope.canSaveSelection()).toBe(true);
    });
  });

  describe("getSaveSelectionText", function() {
    it("returns 'Saving...' when saving", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.saving = true;
      expect(scope.getSaveSelectionText()).toBe("Saving...");
    });

    it("returns 'Update selection' when not saving", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.saving = false;
      expect(scope.getSaveSelectionText()).toBe("Update selection");
    });
  });

  describe("canStopImport", function() {
    it("returns false if saving", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.saving = true;
      expect(scope.canStopImport()).toBe(false);
    });

    it("returns false if stopping", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.stopping = true;
      expect(scope.canStopImport()).toBe(false);
    });

    it("returns true if not saving or stopping", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.saving = false;
      scope.stopping = false;
      expect(scope.canStopImport()).toBe(true);
    });
  });

  describe("getStopImportText", function() {
    it("returns 'Stopping...' when stopping", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.stopping = true;
      expect(scope.getStopImportText()).toBe("Stopping...");
    });

    it("returns 'Stop import' when not stopping", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.stopping = false;
      expect(scope.getStopImportText()).toBe("Stop import");
    });
  });

  describe("stopImport", function() {
    it("does nothing if cannot stop", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      spyOn(scope, "canStopImport").and.returnValue(false);
      spyOn(BootResourcesManager, "stopImport");
      scope.stopImport();
      expect(BootResourcesManager.stopImport).not.toHaveBeenCalled();
    });

    it("calls BootResourcesManager.stopImport", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var defer = $q.defer();
      spyOn(scope, "canStopImport").and.returnValue(true);
      spyOn(BootResourcesManager, "stopImport").and.returnValue(defer.promise);
      scope.stopImport();
      expect(scope.stopping).toBe(true);
      defer.resolve();
      $scope.$digest();
      expect(scope.stopping).toBe(false);
    });
  });

  describe("saveSelection", function() {
    it("passes selected releases and arches", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var defer = $q.defer();
      spyOn(BootResourcesManager, "saveUbuntu").and.returnValue(defer.promise);
      spyOn(scope, "canSaveSelection").and.returnValue(true);

      var release = makeName("release");
      scope.source.selections.releases = [
        {
          name: release
        }
      ];
      var arch = makeName("arch");
      scope.source.selections.arches = [
        {
          name: arch
        }
      ];
      scope.saveSelection();

      expect(scope.saving).toBe(true);
      expect(BootResourcesManager.saveUbuntu).toHaveBeenCalledWith({
        source_type: "maas.io",
        releases: [release],
        arches: [arch]
      });
    });

    it("clears saving and calls updateSource", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var defer = $q.defer();
      spyOn(BootResourcesManager, "saveUbuntu").and.returnValue(defer.promise);
      spyOn(scope, "canSaveSelection").and.returnValue(true);

      var release = makeName("release");
      scope.source.selections.releases = [
        {
          name: release
        }
      ];
      var arch = makeName("arch");
      scope.source.selections.arches = [
        {
          name: arch
        }
      ];
      scope.source.isNew = true;
      scope.source.selections.changed = true;
      spyOn(scope, "updateSource");
      scope.saveSelection();

      expect(scope.saving).toBe(true);
      defer.resolve();
      $scope.$digest();
      expect(scope.saving).toBe(false);
      expect(scope.source.isNew).toBe(false);
      expect(scope.source.selections.changed).toBe(false);
      expect(scope.updateSource).toHaveBeenCalled();
    });
  });

  describe("updateSource", function() {
    it("sets to new and custom when no source", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      scope.bootResources.ubuntu = {
        sources: []
      };
      scope.updateSource();
      expect(scope.source.isNew).toBe(true);
      expect(scope.source.source_type).toBe("custom");
      expect(scope.source.errorMessage).toBe("Currently no source exists.");
    });

    it("sets releases and arches and selections when source", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var source = {
        source_type: "custom",
        url: makeName("url"),
        keyring_filename: makeName("keyring_filename"),
        keyring_data: makeName("keyring_data")
      };
      var release = {
        name: makeName("release"),
        checked: false
      };
      var releaseChecked = {
        name: makeName("release"),
        checked: true
      };
      var arch = {
        name: makeName("arch"),
        checked: false
      };
      var archChecked = {
        name: makeName("arch"),
        checked: true
      };
      scope.bootResources.ubuntu = {
        sources: [source],
        releases: [release, releaseChecked],
        arches: [arch, archChecked]
      };
      spyOn(scope, "regenerateUbuntuImages");
      scope.updateSource();
      expect(scope.source.isNew).toBe(false);
      expect(scope.source.source_type).toBe("custom");
      expect(scope.source.url).toBe(source.url);
      expect(scope.source.keyring_filename).toBe(source.keyring_filename);
      expect(scope.source.keyring_data).toBe(source.keyring_data);
      expect(scope.source.releases).toBe(scope.bootResources.ubuntu.releases);
      expect(scope.source.arches).toBe(scope.bootResources.ubuntu.arches);
      expect(scope.source.selections.releases).toEqual([releaseChecked]);
      expect(scope.source.selections.arches).toEqual([archChecked]);
      expect(scope.regenerateUbuntuImages).toHaveBeenCalled();
    });

    it("sets tooMany when multiple sources", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var release = {
        name: makeName("release"),
        checked: false
      };
      var releaseChecked = {
        name: makeName("release"),
        checked: true
      };
      var arch = {
        name: makeName("arch"),
        checked: false
      };
      var archChecked = {
        name: makeName("arch"),
        checked: true
      };
      scope.bootResources.ubuntu = {
        sources: [{}, {}],
        releases: [release, releaseChecked],
        arches: [arch, archChecked]
      };
      spyOn(scope, "regenerateUbuntuImages");
      scope.updateSource();
      expect(scope.source.isNew).toBe(false);
      expect(scope.source.tooMany).toBe(true);
      expect(scope.source.releases).toBe(scope.bootResources.ubuntu.releases);
      expect(scope.source.arches).toBe(scope.bootResources.ubuntu.arches);
      expect(scope.source.selections.releases).toEqual([releaseChecked]);
      expect(scope.source.selections.arches).toEqual([archChecked]);
      expect(scope.regenerateUbuntuImages).toHaveBeenCalled();
    });
  });

  describe("toggleUbuntuCoreSelection", function() {
    it("toggles checked and sets changed", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = {
        checked: true
      };
      spyOn(scope, "regenerateUbuntuCoreImages");
      scope.toggleUbuntuCoreSelection(image);
      expect(scope.ubuntu_core.changed).toBe(true);
      expect(image.checked).toBe(false);
      expect(scope.regenerateUbuntuCoreImages).toHaveBeenCalled();
    });
  });

  describe("saveUbuntuCoreSelection", function() {
    it("passes correct params and toggles saving", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = {
        name: makeName("name"),
        checked: true
      };
      scope.ubuntu_core.images = [image];
      var defer = $q.defer();
      spyOn(BootResourcesManager, "saveUbuntuCore").and.returnValue(
        defer.promise
      );
      scope.saveUbuntuCoreSelection();

      expect(scope.saving).toBe(true);
      expect(BootResourcesManager.saveUbuntuCore).toHaveBeenCalledWith({
        images: [image.name]
      });
      defer.resolve();
      $scope.$digest();
      expect(scope.saving).toBe(false);
    });
  });

  describe("toggleOtherSelection", function() {
    it("toggles checked and sets changed", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = {
        checked: true
      };
      spyOn(scope, "regenerateOtherImages");
      scope.toggleOtherSelection(image);
      expect(scope.other.changed).toBe(true);
      expect(image.checked).toBe(false);
      expect(scope.regenerateOtherImages).toHaveBeenCalled();
    });
  });

  describe("saveOtherSelection", function() {
    it("passes correct params and toggles saving", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = {
        name: makeName("name"),
        checked: true
      };
      scope.other.images = [image];
      var defer = $q.defer();
      spyOn(BootResourcesManager, "saveOther").and.returnValue(defer.promise);
      scope.saveOtherSelection();

      expect(scope.saving).toBe(true);
      expect(BootResourcesManager.saveOther).toHaveBeenCalledWith({
        images: [image.name]
      });
      defer.resolve();
      $scope.$digest();
      expect(scope.saving).toBe(false);
    });
  });

  describe("canBeRemoved", function() {
    it("returns false if no resourceId", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      expect(scope.canBeRemoved({})).toBe(false);
    });

    it("returns true when title matches a deleted release", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var title = makeName("title");
      var release = {
        title: title,
        deleted: true
      };
      var image = {
        resourceId: makeInteger(0, 100),
        title: title
      };
      scope.bootResources = {
        ubuntu: {
          releases: [release]
        }
      };
      expect(scope.canBeRemoved(image)).toBe(true);
    });

    it("returns true when arch matches a deleted arch", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var title = makeName("title");
      var archName = makeName("arch");
      var release = {
        title: title,
        deleted: false
      };
      var arch = {
        name: archName,
        deleted: true
      };
      var image = {
        resourceId: makeInteger(0, 100),
        title: title,
        arch: archName
      };
      scope.bootResources = {
        ubuntu: {
          releases: [release],
          arches: [arch]
        }
      };
      expect(scope.canBeRemoved(image)).toBe(true);
    });

    it("returns false when release and arch not deleted", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var title = makeName("title");
      var archName = makeName("arch");
      var release = {
        title: title,
        deleted: false
      };
      var arch = {
        name: archName,
        deleted: false
      };
      var image = {
        resourceId: makeInteger(0, 100),
        title: title,
        arch: archName
      };
      scope.bootResources = {
        ubuntu: {
          releases: [release],
          arches: [arch]
        }
      };
      expect(scope.canBeRemoved(image)).toBe(false);
    });
  });

  describe("deleteImage", function() {
    it("sets ubuntuDeleteId", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = {
        resourceId: makeInteger(0, 100)
      };
      scope.deleteImage(image);
      expect(scope.ubuntuDeleteId).toBe(image.resourceId);
    });

    it("clears ubuntuDeleteId", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = {
        resourceId: makeInteger(0, 100)
      };
      scope.deleteImage(image);
      scope.deleteImage();
      expect(scope.ubuntuDeleteId).toBeNull();
    });
  });

  describe("confirmDeleteImage", function() {
    it("calls deleteImage and clears ubuntuDeleteId", function() {
      var directive = compileDirective();
      var scope = directive.isolateScope();
      var image = {
        resourceId: makeInteger(0, 100)
      };
      scope.deleteImage(image);
      spyOn(BootResourcesManager, "deleteImage");
      scope.confirmDeleteImage();
      expect(BootResourcesManager.deleteImage).toHaveBeenCalledWith({
        id: image.resourceId
      });
      expect(scope.ubuntuDeleteId).toBeNull();
    });
  });
});
