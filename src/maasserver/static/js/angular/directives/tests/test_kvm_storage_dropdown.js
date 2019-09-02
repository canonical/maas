/* Copyright 2019 Canonical Ltd.  This software is lecensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for KVM storage dropdown directive.
 */

describe("kvmStorageDropdown", () => {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Preload the $templateCache with empty contents. We only test the
  // controller of the directive, not the template.
  let $templateCache;
  beforeEach(inject($injector => {
    $templateCache = $injector.get("$templateCache");
    $templateCache.put(
      "static/partials/pod-details/kvm-storage-dropdown.html",
      ""
    );
  }));

  // Create a new scope before each test.
  let $scope;
  beforeEach(inject($rootScope => {
    $scope = $rootScope.$new();
    $scope.compose = {
      action: {
        name: "compose",
        title: "Compose",
        sentence: "compose"
      },
      obj: {
        storage: [
          {
            type: "local",
            size: 8,
            tags: [],
            pool: {},
            boot: true
          }
        ],
        requests: [],
        interfaces: [$scope.defaultInterface]
      }
    };
    $scope.dropdownOpen = false;
    $scope.pod = null;
    $scope.storage = $scope.compose.obj.storage;
  }));

  // Return the compiled directive.
  const compileDirective = () => {
    let directive;
    const html = [
      "<div>",
      "<kvm-storage-dropdown ",
      "compose='compose' ",
      "pod='pod' ",
      "storage='storage' ",
      "update-requests='updateRequests' ",
      "></kvm-storage-dropdown>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject($compile => {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return angular.element(directive.find("kvm-storage-dropdown"));
  };

  describe("toggleDropdown", () => {
    it("toggles the dropdown being open", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.dropdownOpen = false;

      scope.toggleDropdown();
      expect(scope.dropdownOpen).toEqual(true);
      scope.toggleDropdown();
      expect(scope.dropdownOpen).toEqual(false);
    });
  });

  describe("closeDropdown", () => {
    it("closes the dropdown", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.dropdownOpen = true;

      scope.closeDropdown();
      expect(scope.dropdownOpen).toEqual(false);
      scope.closeDropdown();
      expect(scope.dropdownOpen).toEqual(false);
    });
  });

  describe("poolOverCapacity", () => {
    it(`returns true if current requests are over
      pod storage_pools capacity`, () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      scope.pod = {
        storage_pools: [
          {
            id: 1,
            available: 10000000000 // bytes
          }
        ]
      };
      const storage = {
        pool: {
          id: 1
        }
      };
      scope.compose = {
        obj: {
          requests: [
            {
              poolId: 1,
              size: 1 // gigabytes
            }
          ]
        },
        storage: [storage]
      };
      expect(scope.poolOverCapacity(storage)).toEqual(false);

      scope.compose.obj.requests = [
        {
          poolId: 1,
          size: 1000 // gigabytes
        }
      ];
      expect(scope.poolOverCapacity(storage)).toEqual(true);
    });
  });

  describe("totalStoragePercentage", () => {
    it("calculates the total percentage of used and requested storage", () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const pool = {
        used: 1,
        total: 10
      };
      const thisRequest = 2;
      const otherRequests = 3;

      // ((1 + 2 + 3) / 10) * 100 = 60
      expect(
        scope.totalStoragePercentage(pool, thisRequest, otherRequests)
      ).toEqual(60);
    });
  });

  describe("getOtherRequests", () => {
    it(`calculates the total size of all requests that aren't the current
      request`, () => {
      const directive = compileDirective();
      const scope = directive.isolateScope();
      const pool = {
        id: 1
      };
      const storage = {
        pool: {
          id: 1
        },
        size: 2
      };
      scope.compose = {
        obj: {
          requests: [
            {
              poolId: 1,
              size: 3
            },
            {
              poolId: 2,
              size: 1
            }
          ]
        }
      };

      expect(scope.getOtherRequests(pool, storage)).toEqual(1);
    });
  });
});
