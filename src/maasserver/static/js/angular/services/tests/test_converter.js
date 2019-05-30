/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ConverterService.
 */

describe("ConverterService", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the ConverterService.
  var ConverterService;
  beforeEach(inject(function($injector) {
    ConverterService = $injector.get("ConverterService");
  }));

  describe("bytesToUnits", function() {
    var scenarios = [
      {
        input: "99",
        output: {
          original: 99,
          converted: 99,
          units: "bytes",
          string: "99 bytes"
        }
      },
      {
        input: 99,
        output: {
          original: 99,
          converted: 99,
          units: "bytes",
          string: "99 bytes"
        }
      },
      {
        input: 8100,
        output: {
          original: 8100,
          converted: 8.1,
          units: "kB",
          string: "8.1 kB"
        }
      },
      {
        input: 8100000,
        output: {
          original: 8100000,
          converted: 8.1,
          units: "MB",
          string: "8.1 MB"
        }
      },
      {
        input: 8100000000,
        output: {
          original: 8100000000,
          converted: 8.1,
          units: "GB",
          string: "8.1 GB"
        }
      },
      {
        input: 8100000000000,
        output: {
          original: 8100000000000,
          converted: 8.1,
          units: "TB",
          string: "8.1 TB"
        }
      },
      {
        input: 8100000000000000,
        output: {
          original: 8100000000000000,
          converted: 8100,
          units: "TB",
          string: "8100.0 TB"
        }
      }
    ];

    angular.forEach(scenarios, function(scenario) {
      it("converts: " + scenario.input, function() {
        var result = ConverterService.bytesToUnits(scenario.input);
        expect(result).toEqual(scenario.output);
      });
    });
  });

  describe("unitsToBytes", function() {
    var scenarios = [
      {
        input: "99",
        units: "bytes",
        output: 99
      },
      {
        input: 99,
        units: "bytes",
        output: 99
      },
      {
        input: 8.1,
        units: "kB",
        output: 8100
      },
      {
        input: 8.1,
        units: "MB",
        output: 8100000
      },
      {
        input: 8.1,
        units: "GB",
        output: 8100000000
      },
      {
        input: 8.1,
        units: "TB",
        output: 8100000000000
      },
      {
        input: 8100,
        units: "TB",
        output: 8100000000000000
      }
    ];

    angular.forEach(scenarios, function(scenario) {
      it("converts: " + scenario.input + scenario.units, function() {
        var result = ConverterService.unitsToBytes(
          scenario.input,
          scenario.units
        );
        expect(result).toBe(scenario.output);
      });
    });
  });

  describe("roundUnits", function() {
    var scenarios = [
      {
        input: "99",
        units: "bytes",
        output: 99
      },
      {
        input: 99,
        units: "bytes",
        output: 99
      },
      {
        input: 8.14,
        units: "kB",
        output: 8090
      },
      {
        input: 8.14,
        units: "MB",
        output: 8090000
      },
      {
        input: 8.14,
        units: "GB",
        output: 8090000000
      },
      {
        input: 8.14,
        units: "TB",
        output: 8090000000000
      }
    ];

    angular.forEach(scenarios, function(scenario) {
      it("converts: " + scenario.input + scenario.units, function() {
        var result = ConverterService.roundUnits(
          scenario.input,
          scenario.units
        );
        expect(result).toBe(scenario.output);
      });
    });
  });

  describe("roundByBlockSize", function() {
    it("rounds down a block", function() {
      var bytes = 8.1 * 1000 * 1000;
      var block_size = 1024;
      expect(ConverterService.roundByBlockSize(bytes, block_size)).toBe(
        8099840
      );
    });

    it("doesnt round down a block", function() {
      var bytes = 1024 * 1024 * 1024;
      var block_size = 1024;
      expect(ConverterService.roundByBlockSize(bytes, block_size)).toBe(
        1024 * 1024 * 1024
      );
    });
  });

  describe("ipv4ToOctets", function() {
    var scenarios = [
      {
        input: "192.168.1.1",
        output: [192, 168, 1, 1]
      },
      {
        input: "172.16.1.1",
        output: [172, 16, 1, 1]
      },
      {
        input: "10.1.1.1",
        output: [10, 1, 1, 1]
      }
    ];

    angular.forEach(scenarios, function(scenario) {
      it("converts: " + scenario.input, function() {
        var result = ConverterService.ipv4ToOctets(scenario.input);
        expect(result).toEqual(scenario.output);
      });
    });
  });

  describe("ipv4ToInteger", function() {
    var scenarios = [
      {
        input: "192.168.1.1",
        output: 3232235777
      },
      {
        input: "172.16.1.1",
        output: 2886729985
      },
      {
        input: "10.1.1.1",
        output: 167837953
      }
    ];

    angular.forEach(scenarios, function(scenario) {
      it("converts: " + scenario.input, function() {
        var result = ConverterService.ipv4ToInteger(scenario.input);
        expect(result).toEqual(scenario.output);
      });
    });
  });

  describe("ipv6Expand", function() {
    var scenarios = [
      {
        input: "::1",
        output: "0000:0000:0000:0000:0000:0000:0000:0001"
      },
      {
        input: "2001:db8::1",
        output: "2001:0db8:0000:0000:0000:0000:0000:0001"
      },
      {
        input: "2001:db8:1::1",
        output: "2001:0db8:0001:0000:0000:0000:0000:0001"
      },
      {
        input: "2001:db8::",
        output: "2001:0db8:0000:0000:0000:0000:0000:0000"
      }
    ];

    angular.forEach(scenarios, function(scenario) {
      it("expands: " + scenario.input, function() {
        var result = ConverterService.ipv6Expand(scenario.input);
        expect(result).toBe(scenario.output);
      });
    });
  });

  describe("ipv6ToGroups", function() {
    var scenarios = [
      {
        input: "::1",
        output: [0, 0, 0, 0, 0, 0, 0, 1]
      },
      {
        input: "2001:db8::1",
        output: [8193, 3512, 0, 0, 0, 0, 0, 1]
      },
      {
        input: "2001:db8:1::1",
        output: [8193, 3512, 1, 0, 0, 0, 0, 1]
      }
    ];

    angular.forEach(scenarios, function(scenario) {
      it("converts: " + scenario.input, function() {
        var result = ConverterService.ipv6ToGroups(scenario.input);
        expect(result).toEqual(scenario.output);
      });
    });
  });
});
