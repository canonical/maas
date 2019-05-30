/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for BrowserService.
 */

import { makeName } from "testing/utils";

describe("BrowserService", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Inject a fake $window allowing the test
  // to set the user agent string.
  var $window;
  beforeEach(function() {
    $window = {
      navigator: {
        userAgent: ""
      }
    };

    // Inject the fake $window into the provider so
    // when the directive is created if will use this
    // $window object instead of the one provided by
    // angular.
    angular.mock.module(function($provide) {
      $provide.value("$window", $window);
    });
  });

  // Get the $injector so the test can grab the BrowserService.
  var $injector;
  beforeEach(inject(function(_$injector_) {
    $injector = _$injector_;
  }));

  it("browser set to other if none of the regex match", function() {
    $window.navigator.userAgent = makeName("randomBrowser");
    const BrowserService = $injector.get("BrowserService");
    expect(BrowserService.browser).toBe("other");
  });

  var scenarios = [
    {
      browser: "chrome",
      userAgent:
        "Mozilla/5.0 (X11; Linux x86_64) " +
        "AppleWebKit/537.36 (KHTML, like Gecko) " +
        "Chrome/41.0.2272.89 Safari/537.36"
    },
    {
      browser: "safari",
      userAgent:
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_9_3) " +
        "AppleWebKit/537.75.14 (KHTML, like Gecko) Version/7.0.3 " +
        "Safari/7046A194A"
    },
    {
      browser: "firefox",
      userAgent:
        "Mozilla/5.0 (X11; Ubuntu; " +
        "Linux x86_64; rv:37.0) Gecko/20100101 Firefox/37.0"
    },
    {
      browser: "ie",
      userAgent:
        "Mozilla/5.0 (compatible, MSIE 11, Windows NT 6.3; " +
        "Trident/7.0; rv:11.0) like Gecko"
    }
  ];

  angular.forEach(scenarios, function(scenario) {
    it("browser set to " + scenario.browser, function() {
      $window.navigator.userAgent = scenario.userAgent;
      const BrowserService = $injector.get("BrowserService");
      expect(BrowserService.browser).toBe(scenario.browser);
    });
  });
});
