/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for machines table directive.
 */

describe("maasMachinesTable", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Preload the $templateCache with empty contents. We only test the
    // controller of the directive, not the template.
    var $q, $templateCache;
    beforeEach(inject(function($injector) {
        $q = $injector.get('$q');
        $templateCache = $injector.get('$templateCache');
        $templateCache.put(
            "static/partials/machines-table.html?v=undefined", '');
    }));

    // Load the required managers.
    var MachinesManager, GeneralManager, ManagerHelperService;
    beforeEach(inject(function($injector) {
        MachinesManager = $injector.get('MachinesManager');
        GeneralManager = $injector.get('GeneralManager');
        ManagerHelperService = $injector.get('ManagerHelperService');
    }));

    // Create a new scope before each test.
    var $scope;
    beforeEach(inject(function($rootScope) {
        $scope = $rootScope.$new();
    }));

    // Makes a machine.
    function makeMachine() {
        var machine = {
            system_id: makeName("system_id"),
            $selected: false
        };
        MachinesManager._items.push(machine);
        return machine;
    }

    // Return the compiled directive with the items from the scope.
    function compileDirective(design) {
        var directive;
        var html = [
            '<div>',
                '<maas-machines-table ',
                  'on-listing-change="onListingChange($machines)" ',
                  'on-check-all="onCheckAll()" ',
                  'on-check="onCheck($machine)"></maas-machines-table>',
            '</div>'
            ].join('');

        // Compile the directive.
        inject(function($compile) {
            directive = $compile(html)($scope);
        });

        // Perform the digest cycle to finish the compile.
        $scope.$digest();
        return directive.find("maas-machines-table");
    }

    it("sets initial variables", function() {
        var directive = compileDirective();
        var scope = directive.isolateScope();
        expect(scope.table).toEqual({
          column: 'fqdn',
          predicate: 'fqdn',
          reverse: false,
          allViewableChecked: false,
          machines: MachinesManager.getItems(),
          filteredMachines: [],
          osinfo: GeneralManager.getData("osinfo")
        });
        expect(scope.table.machines).toBe(MachinesManager.getItems());
    });

    describe("updateAllChecked", function() {

        it("sets allViewableChecked to false when no machines", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            scope.table.allViewableChecked = true;
            scope.table.filteredMachines = [];
            scope.updateAllChecked();
            expect(scope.table.allViewableChecked).toBe(false);
        });

        it("sets allViewableChecked to false when one not selected",
            function() {
                var directive = compileDirective();
                var scope = directive.isolateScope();
                scope.table.allViewableChecked = true;
                scope.table.filteredMachines = [{
                    $selected: true
                }, {
                    $selected: false
                }];
                scope.updateAllChecked();
                expect(scope.table.allViewableChecked).toBe(false);
            });

        it("sets allViewableChecked to false when one not selected",
            function() {
                var directive = compileDirective();
                var scope = directive.isolateScope();
                scope.table.filteredMachines = [{
                    $selected: true
                }, {
                    $selected: true
                }];
                scope.updateAllChecked();
                expect(scope.table.allViewableChecked).toBe(true);
            });
    });

    describe("toggleCheckAll", function() {

        it("unselected all selected machines", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var machine = makeMachine();
            MachinesManager.selectItem(machine.system_id);
            scope.table.allViewableChecked = true;
            scope.table.filteredMachines = [machine];
            scope.toggleCheckAll();
            expect(machine.$selected).toBe(false);
            expect(scope.table.allViewableChecked).toBe(false);
        });

        it("selects all unselected machines", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var machine = makeMachine();
            scope.table.allViewableChecked = false;
            scope.table.filteredMachines = [machine];
            scope.toggleCheckAll();
            expect(machine.$selected).toBe(true);
            expect(scope.table.allViewableChecked).toBe(true);
        });

        it("calls onCheckAll", function() {
            $scope.onCheckAll = jasmine.createSpy("onCheckAll");
            var directive = compileDirective();
            var scope = directive.isolateScope();
            scope.toggleCheckAll();
            expect($scope.onCheckAll).toHaveBeenCalled();
        });
    });

    describe("toggleChecked", function() {

        it("selects machine", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var machine = makeMachine();
            scope.table.filteredMachines = [machine];
            scope.toggleChecked(machine);
            expect(machine.$selected).toBe(true);
            expect(scope.table.allViewableChecked).toBe(true);
        });

        it("unselects machine", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var machine = makeMachine();
            scope.table.filteredMachines = [machine];
            MachinesManager.selectItem(machine.system_id);
            scope.toggleChecked(machine);
            expect(machine.$selected).toBe(false);
            expect(scope.table.allViewableChecked).toBe(false);
        });
    });

    describe("sortTable", function() {

        it("sets predicate", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var predicate = makeName('predicate');
            scope.sortTable(predicate);
            expect(scope.table.predicate).toBe(predicate);
        });

        it("reverses reverse", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            scope.table.reverse = true;
            scope.sortTable(makeName('predicate'));
            expect(scope.table.reverse).toBe(false);
        });
    });

    describe("selectColumnOrSort", function() {

        it("sets column if different", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var column = makeName('column');
            scope.selectColumnOrSort(column);
            expect(scope.table.column).toBe(column);
        });

        it("calls sortTable if column already set", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var column = makeName('column');
            scope.table.column = column;
            spyOn(scope, "sortTable");
            scope.selectColumnOrSort(column);
            expect(scope.sortTable).toHaveBeenCalledWith(column);
        });
    });

    describe("showSpinner", function() {

        it("returns false/true based on status codes", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var STATUSES = [1, 9, 12, 14, 17, 19];
            var i;
            for(i = 0; i < 20; i++) {
                var machine = {
                    status_code: i
                };
                var expected = false;
                if(STATUSES.indexOf(i) > -1) {
                    expected = true;
                }
                expect(scope.showSpinner(machine)).toBe(expected);
            }
        });
    });

    describe("showFailedTestWarning", function() {

        var spinner_statuses = [0, 1, 2, 21, 22];
        var testing_statuses = [-1, 2];

        it("returns false when showing spinner", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            spyOn(scope, "showSpinner").and.returnValue(true);
            expect(scope.showFailedTestWarning({})).toBe(false);
        });

        it("returns false when testing or commissioning", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            spyOn(scope, "showSpinner").and.returnValue(false);
            angular.forEach(spinner_statuses, function(status) {
                var machine = {
                    status_code: status
                };
                expect(scope.showFailedTestWarning(machine)).toBe(false);
            });
        });

        it("returns false when testing_status is passed/unknown", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            spyOn(scope, "showSpinner").and.returnValue(false);
            angular.forEach(testing_statuses, function(testing_status) {
                var machine = {
                    status_code: 4, // READY
                    testing_status: testing_status
                };
                expect(scope.showFailedTestWarning(machine)).toBe(false);
            });
        });

        it("returns true otherwise", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            spyOn(scope, "showSpinner").and.returnValue(false);
            var i, j;
            // Go through all known statuses
            for(i = 0; i <= 22; i++) {
                if(spinner_statuses.indexOf(i) === -1) {
                    // Go through all known script statuses
                    for(j = -1; j <= 8; j++) {
                        if(testing_statuses.indexOf(j) === -1 ) {
                            var machine = {
                                status_code: i,
                                testing_status: j
                            };
                            expect(scope.showFailedTestWarning(machine)).toBe(
                                true);
                        }
                    }
                }
            }
        });
    });

    describe("showNodeStatus", function() {

        it("returns false when showing spinner", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            spyOn(scope, "showSpinner").and.returnValue(true);
            spyOn(scope, "showFailedTestWarning").and.returnValue(false);
            var machine = {
                other_status_status: 3
            };
            expect(scope.showNodeStatus(machine)).toBe(false);
        });

        it("returns false when showing failed test warning", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            spyOn(scope, "showSpinner").and.returnValue(false);
            spyOn(scope, "showFailedTestWarning").and.returnValue(true);
            var machine = {
                other_test_status: 3
            };
            expect(scope.showNodeStatus(machine)).toBe(false);
        });

        it("returns false when other_test_status is passed", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            spyOn(scope, "showSpinner").and.returnValue(false);
            spyOn(scope, "showFailedTestWarning").and.returnValue(false);
            var machine = {
                other_test_status: 2
            };
            expect(scope.showNodeStatus(machine)).toBe(false);
        });

        it("returns true otherwise", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            spyOn(scope, "showSpinner").and.returnValue(false);
            spyOn(scope, "showFailedTestWarning").and.returnValue(false);
            var machine = {
                other_status_status: 3
            };
            expect(scope.showNodeStatus(machine)).toBe(true);
        });
    });

    describe("getReleaseTitle", function() {

        it("returns release title from osinfo", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            scope.table.osinfo = {
                releases: [
                    ['ubuntu/xenial', 'Ubuntu Xenial']
                ]
            };
            expect(scope.getReleaseTitle('ubuntu/xenial')).toBe(
                'Ubuntu Xenial');
        });

        it("returns release name when not in osinfo", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            scope.table.osinfo = {
                releases: []
            };
            expect(scope.getReleaseTitle('ubuntu/xenial')).toBe(
                'ubuntu/xenial');
        });

        it("returns release name when osinfo.releases undefined", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            scope.table.osinfo = {
            };
            expect(scope.getReleaseTitle('ubuntu/xenial')).toBe(
                'ubuntu/xenial');
        });
    });

    describe("getStatusText", function() {

        it("returns status text when not deployed or deploying", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var machine = {
                status: makeName("status")
            };

            expect(scope.getStatusText(machine)).toBe(machine.status);
        });

        it("returns status with release title when deploying", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var machine = {
                status: "Deploying",
                osystem: "ubuntu",
                distro_series: "xenial"
            };
            scope.table.osinfo = {
                releases: [
                    ['ubuntu/xenial', 'Ubuntu Xenial']
                ]
            };
            expect(scope.getStatusText(machine)).toBe(
                'Deploying Ubuntu Xenial');
        });

        it("returns release title when deployed", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var machine = {
                status: "Deployed",
                osystem: "ubuntu",
                distro_series: "xenial"
            };
            scope.table.osinfo = {
                releases: [
                    ['ubuntu/xenial', 'Ubuntu Xenial']
                ]
            };
            expect(scope.getStatusText(machine)).toBe(
                'Ubuntu Xenial');
        });

        it("returns release title without codename when deployed", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var machine = {
                status: "Deployed",
                osystem: "ubuntu",
                distro_series: "xenial"
            };
            scope.table.osinfo = {
                releases: [
                    ['ubuntu/xenial', 'Ubuntu 16.04 LTS "Xenial Xerus"']
                ]
            };
            expect(scope.getStatusText(machine)).toBe(
                'Ubuntu 16.04 LTS');
        });
    });

    describe("onListingChange", function() {

        it("called when filteredMachines changes", function() {
            $scope.onListingChange = jasmine.createSpy('onListingChange');
            var directive = compileDirective();
            var scope = directive.isolateScope();

            var machines = [{}];
            scope.table.filteredMachines = machines;

            $scope.$digest();
            expect($scope.onListingChange).toHaveBeenCalledWith(machines);
        });
    });

    describe("formatMemoryUnit", function() {

        it("returns unit and value separately", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var memory = Math.floor(Math.random() * 10) + 1;
            var formattedMemory = scope.formatMemoryUnit(memory);

            var actual = Object.keys(formattedMemory).sort();
            var expected = ['unit', 'value'];
            expect(actual).toEqual(expected);
        });

        it("removes leading zeroes and converts to string", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var rand = Math.floor(Math.random() * 10) + 1;
            var memory = rand.toFixed(1);

            var actual = scope.formatMemoryUnit(memory).value;
            var expected = rand.toString();
            expect(actual).toEqual(expected);
        });
    });

    describe("formatStorageUnit", function() {

        it("returns unit and value separately", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var storage = Math.random().toFixed(1) * 100;
            var formattedStorage = scope.formatStorageUnit(storage);

            var actual = Object.keys(formattedStorage).sort();
            var expected = ['unit', 'value'];
            expect(actual).toEqual(expected);
        });

        it("displays three significant figures", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var storage = Math.random() * 10;

            var actual = scope.formatStorageUnit(storage).value;
            var expected = Number(storage.toPrecision(3)).toString();
            expect(actual).toEqual(expected);
        });

        it("converts unit to TB at or above 1000 GB", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var storage = 1000.0;

            var actual = scope.formatStorageUnit(storage);
            var expected = {
                unit: 'TB',
                value: '1',
            }
            expect(actual).toEqual(expected);
        });
    });

    describe("getBootIp", function() {

        it("returns the machine's boot IP address if it exists", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var ipAddresses = [{
                "ip": '172.168.1.1',
                "is_boot": false,
            }, {
                "ip": '172.168.1.2',
                "is_boot": true,
            }];

            var actual = scope.getBootIp(ipAddresses);
            var expected = '172.168.1.2';
            expect(actual).toEqual(expected);
        });
    });

    describe("removeDuplicates", function() {

        it("returns a unique IP object with a duplicate", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var ipAddresses = [{
                "ip": '172.168.1.1',
                "is_boot": false,
            }, {
                "ip": '172.168.1.2',
                "is_boot": true,
            }, {
                "ip": '172.168.1.2',
                "is_boot": true,
            }];

            var actual = scope.removeDuplicates(ipAddresses, 'ip');
            expect(actual.length).toEqual(2);
        });

        it("returns a unique IP object without a duplicate", function() {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var ipAddresses = [{
                "ip": '172.168.1.1',
                "is_boot": false,
            }, {
                "ip": '172.168.1.2',
                "is_boot": true,
            }, {
                "ip": '172.168.1.3',
                "is_boot": true,
            }];

            var actual = scope.removeDuplicates(ipAddresses, 'ip');
            expect(actual.length).toEqual(3);
        });
    });

    describe("changePowerState", function() {

        it(`executes MachinesManager.checkPowerState
            if action param is "check"`, () => {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var machine = makeMachine();
            spyOn(MachinesManager, "checkPowerState")
                .and.returnValue($q.defer().promise);

            scope.changePowerState(machine, "check");
            expect(MachinesManager.checkPowerState)
                .toHaveBeenCalledWith(machine);
        });

        it("executes MachinesManager.performAction correctly", () => {
            var directive = compileDirective();
            var scope = directive.isolateScope();
            var machine = makeMachine();
            spyOn(MachinesManager, "performAction")
                .and.returnValue($q.defer().promise);

            scope.changePowerState(machine, "on");
            expect(MachinesManager.performAction)
                .toHaveBeenCalledWith(machine, "on");
        });
    });
});
