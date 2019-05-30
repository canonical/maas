/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for default OS select.
 */

describe("maasDefaultOSSelect", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Create a new scope before each test. Not used in this test, but
  // required to compile the directive.
  var $scope;
  beforeEach(inject(function($rootScope) {
    $scope = $rootScope.$new();
  }));

  // Return the compiled directive with the items from the scope.
  function compileDirective() {
    var directive;
    var html = [
      "<div>",
      '<div maas-default-os-select="#os-select" ',
      'maas-default-series-select="#series-select">',
      '<select name="os" id="os-select">',
      '<option value="ubuntu" ',
      'selected="selected">Ubuntu</option>',
      '<option value="centos">CentOS</option>',
      "</select>",
      '<select name="series" id="series-select">',
      '<option value="ubuntu/trusty" ',
      'selected="selected">Trusty</option>',
      '<option value="ubuntu/xenial">Xenial</option>',
      '<option value="ubuntu/bionic">Bionic</option>',
      '<option value="centos/centos6">CentOS 6</option>',
      '<option value="centos/centos7">CentOS 7</option>',
      "</select>",
      "</div>"
    ].join("");

    // Compile the directive.
    inject(function($compile) {
      directive = $compile(html)($scope);
    });

    // Perform the digest cycle to finish the compile.
    $scope.$digest();

    // Attach to document so it can grab focus.
    directive.appendTo(document.body);
    return directive.find("div[maas-default-os-select]");
  }

  // Compile the directive.
  var directive;
  beforeEach(function() {
    directive = compileDirective();
  });

  // Return the values of the visible options.
  var getVisibleOptions = function(directive) {
    var options = directive.find("#series-select > option");
    var visible = [];
    angular.forEach(options, function(option) {
      option = angular.element(option);
      if (!option.hasClass("u-hide")) {
        visible.push(option.val());
      }
    });
    return visible.sort();
  };

  it("hides other series on load", function() {
    var expected = ["ubuntu/bionic", "ubuntu/trusty", "ubuntu/xenial"];
    var visible = getVisibleOptions(directive);
    expect(expected).toEqual(visible);
  });

  it("hide other series on change", function() {
    var osSelect = directive.find("#os-select");
    osSelect.val("centos").trigger("change");

    var expected = ["centos/centos6", "centos/centos7"];
    var visible = getVisibleOptions(directive);
    expect(expected).toEqual(visible);
  });

  it("sets first series on change", function() {
    var osSelect = directive.find("#os-select");
    osSelect.val("centos").trigger("change");

    var seriesSelect = directive.find("#series-select");
    expect(seriesSelect.val()).toEqual("centos/centos6");
  });
});
