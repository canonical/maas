/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for JSONService.
 */

describe("JSONService", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Load the JSONService.
  var JSONService;
  beforeEach(inject(function($injector) {
    JSONService = $injector.get("JSONService");
  }));

  describe("tryParse", function() {
    var scenarios = [
      {
        input: null,
        output: null
      },
      {
        input: false,
        output: null
      },
      {
        input: 123,
        output: null
      },
      {
        input: undefined,
        output: null
      },
      {
        input: "string",
        output: null
      },
      {
        input: angular.toJson({ data: "string" }),
        output: {
          data: "string"
        }
      }
    ];

    angular.forEach(scenarios, function(scenario) {
      it("parses: " + scenario.input, function() {
        var result = JSONService.tryParse(scenario.input);
        expect(result).toEqual(scenario.output);
      });
    });
  });
});
