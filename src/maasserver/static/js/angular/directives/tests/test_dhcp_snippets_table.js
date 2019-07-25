/* Copyright 2019 Canonical Ltd.  This software is lecensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for DHCP snippets table directive.
 */

import { makeInteger, makeName } from "testing/utils";

describe("maasDhcpSnippetsTable", () => {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Preload the $templateCache with empty contents. We only test the
  // controller of the directive, not the template.
  let $templateCache;
  let $q;
  let $log;

  beforeEach(inject($injector => {
    $templateCache = $injector.get("$templateCache");
    $q = $injector.get("$q");
    $log = $injector.get("$log");
    $templateCache.put(
      "static/partials/dhcp-snippets-table.html?v=undefined",
      ""
    );
  }));

  // Load the required managers.
  let SubnetsManager;
  let MachinesManager;
  let DevicesManager;
  let ControllersManager;
  let DHCPSnippetsManager;

  beforeEach(inject(function($injector) {
    SubnetsManager = $injector.get("SubnetsManager");
    MachinesManager = $injector.get("MachinesManager");
    DevicesManager = $injector.get("DevicesManager");
    ControllersManager = $injector.get("ControllersManager");
    DHCPSnippetsManager = $injector.get("DHCPSnippetsManager");
  }));

  // Create a new scope before each test.
  let $scope;

  beforeEach(inject($rootScope => {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective() {
    let directive;
    let html = [
      "<div>",
      "<maas-dhcp-snippets-table></maas-dhcp-snippets-table>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject($compile => {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("maas-dhcp-snippets-table");
  }

  // Make a fake snippet.
  let _nextId = 0;

  function makeSnippet() {
    return {
      id: _nextId++,
      name: makeName("snippet"),
      enabled: true,
      value: makeName("value")
    };
  }

  it("sets initial values", () => {
    const directive = compileDirective();
    const scope = directive.isolateScope();
    expect(scope.snippetsManager).toBe(DHCPSnippetsManager);
    expect(scope.subnets).toBe(SubnetsManager.getItems());
    expect(scope.machines).toBe(MachinesManager.getItems());
    expect(scope.devices).toBe(DevicesManager.getItems());
    expect(scope.controllers).toBe(ControllersManager.getItems());
    expect(scope.newSnippet).toBeNull();
    expect(scope.editSnippet).toBeNull();
    expect(scope.deleteSnippet).toBeNull();
    expect(scope.snippetTypes).toEqual(["Global", "Subnet", "Node"]);
  });

  describe("getSnippetTypeText", () => {
    it("returns 'Node'", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      let snippet = makeSnippet();
      snippet.node = makeName("system_id");
      expect(scope.getSnippetTypeText(snippet)).toBe("Node");
    });

    it("returns 'Subnet'", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      let snippet = makeSnippet();
      snippet.subnet = makeInteger();
      expect(scope.getSnippetTypeText(snippet)).toBe("Subnet");
    });

    it("returns 'Global'", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      let snippet = makeSnippet();
      expect(scope.getSnippetTypeText(snippet)).toBe("Global");
    });
  });

  describe("getSnippetAppliesToText", () => {
    it("returns node.fqdn from MachinesManager", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const system_id = makeName("system_id");
      const fqdn = makeName("fqdn");
      let node = {
        system_id: system_id,
        fqdn: fqdn
      };
      let snippet = makeSnippet();
      snippet.node = system_id;
      MachinesManager._items = [node];
      expect(scope.getSnippetAppliesToText(snippet)).toBe(fqdn);
    });

    it("returns device.fqdn from DevicesManager", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const system_id = makeName("system_id");
      const fqdn = makeName("fqdn");
      let device = {
        system_id: system_id,
        fqdn: fqdn
      };
      let snippet = makeSnippet();
      snippet.node = system_id;
      DevicesManager._items = [device];
      expect(scope.getSnippetAppliesToText(snippet)).toBe(fqdn);
    });

    it("returns controller.fqdn from ControllersManager", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const system_id = makeName("system_id");
      const fqdn = makeName("fqdn");
      let controller = {
        system_id: system_id,
        fqdn: fqdn
      };
      let snippet = makeSnippet();
      snippet.node = system_id;
      ControllersManager._items = [controller];
      expect(scope.getSnippetAppliesToText(snippet)).toBe(fqdn);
    });

    it("returns subnet from SubnetsManager", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const subnet_id = makeInteger(0, 100);
      const cidr = makeName("cidr");
      let subnet = {
        id: subnet_id,
        cidr: cidr
      };
      let snippet = makeSnippet();
      snippet.subnet = subnet_id;
      SubnetsManager._items = [subnet];
      expect(scope.getSnippetAppliesToText(snippet)).toBe(cidr);
    });
  });

  describe("getSnippetAppliesToObject", () => {
    it("returns node from MachinesManager", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const system_id = makeName("system_id");
      let node = {
        system_id: system_id
      };
      let snippet = makeSnippet();
      snippet.node = system_id;
      MachinesManager._items = [node];
      expect(scope.getSnippetAppliesToObject(snippet)).toBe(node);
    });

    it("returns device from DevicesManager", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const system_id = makeName("system_id");
      let device = {
        system_id: system_id
      };
      let snippet = makeSnippet();
      snippet.node = system_id;
      DevicesManager._items = [device];
      expect(scope.getSnippetAppliesToObject(snippet)).toBe(device);
    });

    it("returns controller from ControllersManager", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const system_id = makeName("system_id");
      let controller = {
        system_id: system_id
      };
      let snippet = makeSnippet();
      snippet.node = system_id;
      ControllersManager._items = [controller];
      expect(scope.getSnippetAppliesToObject(snippet)).toBe(controller);
    });

    it("returns subnet from SubnetsManager", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      let subnet_id = makeInteger(0, 100);
      let subnet = {
        id: subnet_id
      };
      let snippet = makeSnippet();
      snippet.subnet = subnet_id;
      SubnetsManager._items = [subnet];
      expect(scope.getSnippetAppliesToObject(snippet)).toBe(subnet);
    });
  });

  describe("getNode", () => {
    it("returns node from MachinesManager", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const system_id = makeName("system_id");
      let node = {
        system_id: system_id
      };
      MachinesManager._items = [node];
      expect(scope.getNode(system_id)).toBe(node);
    });

    it("returns node from DevicesManager", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const system_id = makeName("system_id");
      let node = {
        system_id: system_id
      };
      DevicesManager._items = [node];
      expect(scope.getNode(system_id)).toBe(node);
    });

    it("returns node from ControllersManager", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const system_id = makeName("system_id");
      let node = {
        system_id: system_id
      };
      ControllersManager._items = [node];
      expect(scope.getNode(system_id)).toBe(node);
    });
  });

  describe("snippetToggle", () => {
    it("calls updateItem", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const snippet = makeSnippet();
      spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(
        $q.defer().promise
      );
      scope.snippetToggle(snippet);
      expect(DHCPSnippetsManager.updateItem).toHaveBeenCalledWith(snippet);
    });

    it("updateItem reject resets enabled", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const snippet = makeSnippet();
      let defer = $q.defer();
      spyOn(DHCPSnippetsManager, "updateItem").and.returnValue(defer.promise);
      spyOn($log, "error");
      scope.snippetToggle(snippet);
      var errorMsg = makeName("error");
      defer.reject(errorMsg);
      scope.$digest();
      expect(snippet.enabled).toBe(false);
      expect($log.error).toHaveBeenCalledWith(errorMsg);
    });
  });

  describe("snippetEnterEdit", () => {
    it("clears new and delete and sets edit", () => {
      $q.defer();
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const snippet = makeSnippet();
      scope.newSnippet = {};
      scope.deleteSnippet = {};
      scope.snippetEnterEdit(snippet);
      expect(scope.editSnippet).toBe(snippet);
      expect(scope.editSnippet.type).toBe(scope.getSnippetTypeText(snippet));
      expect(scope.newSnippet).toBeNull();
      expect(scope.deleteSnippet).toBeNull();
    });
  });

  describe("snippetExitEdit", () => {
    it("clears editSnippet", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.editSnippet = {};
      scope.snippetExitEdit();
      expect(scope.editSnippet).toBeNull();
    });
  });

  describe("getSubnetName", () => {
    it("calls SubnetsManager.getName", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      let subnet = {};
      let subnetsName = {};
      spyOn(SubnetsManager, "getName").and.returnValue(subnetsName);
      expect(scope.getSubnetName(subnet)).toBe(subnetsName);
      expect(SubnetsManager.getName).toHaveBeenCalledWith(subnet);
    });
  });

  describe("snippetExitRemove", () => {
    it("sets delete to null", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.deleteSnippet = {};
      scope.snippetExitRemove();
      expect(scope.deleteSnippet).toBeNull();
    });
  });

  describe("snippetConfirmRemove", () => {
    it("calls deleteItem and then snippetExitRemove", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      let snippet = makeSnippet();
      let defer = $q.defer();
      spyOn(DHCPSnippetsManager, "deleteItem").and.returnValue(defer.promise);
      spyOn(scope, "snippetExitRemove");
      scope.deleteSnippet = snippet;
      scope.snippetConfirmRemove(snippet);
      expect(DHCPSnippetsManager.deleteItem).toHaveBeenCalledWith(snippet);
      defer.resolve();
      scope.$digest();
      expect(scope.snippetExitRemove).toHaveBeenCalled();
    });
  });

  describe("snippetEnterRemove", () => {
    it("clears new and edit and sets delete", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      let snippet = makeSnippet();
      scope.newSnippet = {};
      scope.editSnippet = {};
      scope.snippetEnterRemove(snippet);
      expect(scope.deleteSnippet).toBe(snippet);
      expect(scope.newSnippet).toBeNull();
      expect(scope.editSnippet).toBeNull();
    });
  });

  describe("snippetAddCancel", () => {
    it("newSnippet gets cleared", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.newSnippet = {};
      scope.snippetAddCancel();
      expect(scope.newSnippet).toBeNull();
    });
  });

  describe("snippetAdd", () => {
    it("sets newSnippet", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.editSnippet = {};
      scope.deleteSnippet = {};
      scope.snippetAdd();
      expect(scope.newSnippet).toEqual({
        name: "",
        type: "Global",
        enabled: true
      });
      expect(scope.editSnippet).toBeNull();
      expect(scope.deleteSnippet).toBeNull();
    });
  });
});
