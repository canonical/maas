/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for release name directive.
 */

import { makeName } from "testing/utils";

describe("maasReleaseName", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective() {
    var directive;
    var html = [
      "<div>",
      '<span data-maas-release-name="release"></span>',
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();
    return directive.find("span");
  }

  it("set blank when doesn't exist on scope", function() {
    var directive = compileDirective();
    expect(directive.text()).toBe("");
  });

  it("sets passed release value when no osinfo", function() {
    $scope.release = makeName("release");
    var directive = compileDirective();
    expect(directive.text()).toBe($scope.release);
  });

  it("sets to title from osinfo", function() {
    var os = makeName("os");
    var release = makeName("release");
    var title = makeName("title");
    var directive = compileDirective();
    var scope = directive.isolateScope();
    scope.osinfo.releases = [[os + "/" + release, title]];
    $scope.release = os + "/" + release;
    $scope.$digest();
    expect(directive.text()).toBe(title);
  });
});
