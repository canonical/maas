/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for ConverterService.
 */

describe("ConverterService", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

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
                    units: "Bytes",
                    string: "99 Bytes"
                }
            },
            {
                input: 99,
                output: {
                    original: 99,
                    converted: 99,
                    units: "Bytes",
                    string: "99 Bytes"
                }
            },
            {
                input: 8100,
                output: {
                    original: 8100,
                    converted: 8.1,
                    units: "KB",
                    string: "8.1 KB"
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
                var result = ConverterService.bytesToUnits(
                    scenario.input);
                expect(result).toEqual(scenario.output);
            });
        });
    });

    describe("unitsToBytes", function() {

        var scenarios = [
            {
                input: "99",
                units: "Bytes",
                output: 99
            },
            {
                input: 99,
                units: "Bytes",
                output: 99
            },
            {
                input: 8.1,
                units: "KB",
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
                    scenario.input, scenario.units);
                expect(result).toBe(scenario.output);
            });
        });
    });

    describe("roundUnits", function() {

        var scenarios = [
            {
                input: "99",
                units: "Bytes",
                output: 99
            },
            {
                input: 99,
                units: "Bytes",
                output: 99
            },
            {
                input: 8.14,
                units: "KB",
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
                    scenario.input, scenario.units);
                expect(result).toBe(scenario.output);
            });
        });
    });

    describe("roundByBlockSize", function() {

        it("rounds down a block", function() {
            var bytes = 8.1 * 1000 * 1000;
            var block_size = 1024;
            expect(ConverterService.roundByBlockSize(bytes, block_size)).toBe(
                8099840);
        });

        it("doesnt round down a block", function() {
            var bytes = 1024 * 1024 * 1024;
            var block_size = 1024;
            expect(ConverterService.roundByBlockSize(bytes, block_size)).toBe(
                1024 * 1024 * 1024);
        });
    });
});
