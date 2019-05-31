/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for LogService.
 */

import { makeName } from "testing/utils";

describe("LogService", function() {
  beforeEach(function() {
    spyOn(console, "debug");
    spyOn(console, "log");
    spyOn(console, "info");
    spyOn(console, "warn");
    spyOn(console, "error");
  });

  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Get the $injector so the test can grab the LogService.
  var $injector;
  var LogService;
  beforeEach(inject(function(_$injector_) {
    $injector = _$injector_;
    LogService = $injector.get("LogService");
  }));

  var scenarios = [
    {
      it: "console.error",
      logLevel: 1,
      func: "error"
    },
    {
      it: "console.warn",
      logLevel: 2,
      func: "warn"
    },
    {
      it: "console.info",
      logLevel: 3,
      func: "info"
    },
    {
      it: "console.log",
      logLevel: 4,
      func: "log"
    },
    {
      it: "console.debug",
      logLevel: 5,
      func: "debug"
    }
  ];

  // Do positive tests for appropriate log levels.
  angular.forEach(scenarios, function(scenario) {
    it(
      "calls " + scenario.it + " for logLevel=" + scenario.logLevel,
      function() {
        LogService.logging = true;
        LogService.logLevel = scenario.logLevel;
        var logFunction = LogService[scenario.func];
        var message = makeName();
        logFunction(message);
        // eslint-disable-next-line no-console
        expect(console[scenario.func]).toHaveBeenCalled();
      }
    );
  });

  // Do negative tests for log levels that do not include the level.
  angular.forEach(scenarios, function(scenario) {
    it(
      "doesn't call " +
        scenario.it +
        " for logLevel=" +
        (scenario.logLevel - 1),
      function() {
        LogService.logging = true;
        LogService.logLevel = scenario.logLevel - 1;
        var logFunction = LogService[scenario.func];
        var message = makeName();
        logFunction(message);
        // eslint-disable-next-line no-console
        expect(console[scenario.func]).not.toHaveBeenCalled();
      }
    );
  });

  describe("formatMilliseconds", function() {
    it("formats milliseconds into equivalent decimal seconds", function() {
      var result = LogService.formatMilliseconds(1234);
      expect(result).toEqual("1.234");
    });

    it("zero-pads values", function() {
      var result = LogService.formatMilliseconds(1000);
      expect(result).toEqual("1.000");
    });
  });

  describe("__log", function() {
    it("appends timestamp to the beginning of the log", function() {
      LogService.logging = true;
      var message = makeName();
      var outMessage = null;
      LogService.now = function() {
        return 0;
      };
      LogService.__log(
        function() {
          // __log() will call the destination log function after
          // appending the formatted time to the beginning.
          outMessage = [arguments[0], arguments[1]];
        },
        [message]
      );
      expect(outMessage).toEqual(["[0.000]", message]);
    });
  });
});
