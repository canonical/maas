/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Add Hardware Controller
 */

angular.module('MAAS').controller('AddHardwareController', [
    '$scope', '$timeout', 'ClustersManager', 'ZonesManager',
    'NodesManager', 'RegionConnection', function($scope, $timeout,
        ClustersManager, ZonesManager, NodesManager, RegionConnection) {

        // Set the addHardwareScope in the parent, so it can call functions
        // in this controller.
        var parentScope = $scope.$parent;
        parentScope.addHardwareScope = $scope;

        // Set initial values.
        $scope.viewable = false;
        $scope.clusters = ClustersManager.getItems();
        $scope.zones = ZonesManager.getItems();
        $scope.architectures = [];
        $scope.macPattern = /^([0-9A-Fa-f]{2}:){5}([0-9A-Fa-f]{2})$/;

        // Input values.
        $scope.machines = [];
        $scope.currentMachine = null;

        // Get the master cluster from the loaded clusters.
        function masterCluster() {
            if($scope.clusters.length === 0) {
                return null;
            } else {
                return $scope.clusters[0];
            }
        }

        // Get the default zone from the loaded zones.
        function defaultZone() {
            if($scope.zones.length === 0) {
                return null;
            } else {
                return $scope.zones[0];
            }
        }

        // Get the default architecture from the loaded architectures.
        function defaultArchitecture() {
            if($scope.architectures.length === 0) {
                return '';
            } else {
                // Return amd64/generic first if available.
                var i;
                for(i = 0; i < $scope.architectures.length; i++) {
                    if($scope.architectures[i] === "amd64/generic") {
                        return $scope.architectures[i];
                    }
                }
                return $scope.architectures[0];
            }
        }

        // Return a new MAC address object.
        function newMAC() {
            return {
                mac: '',
                error: false
            };
        }

        // Return a new machine object.
        function newMachine() {
            // Clone the current machine instead of just creating a new one.
            // This helps the user by already having the previous selected
            // items selected for the new machine.
            if(angular.isObject($scope.currentMachine)) {
                return {
                    cluster: $scope.currentMachine.cluster,
                    name: '',
                    macs: [newMAC()],
                    zone: $scope.currentMachine.zone,
                    architecture: $scope.currentMachine.architecture,
                    power: {
                        type: $scope.currentMachine.power.type,
                        parameters: {}
                    }
                };
            }

            // No current machine. So create a new blank machine.
            return {
                cluster: masterCluster(),
                name: '',
                macs: [newMAC()],
                zone: defaultZone(),
                architecture: defaultArchitecture(),
                power: {
                    type: null,
                    parameters: {}
                }
            };
        }

        // Set the machine a random hostname.
        function setRandomHostname(machine) {
            return RegionConnection.callMethod(
                "general.random_hostname", {}).then(
                    function(hostname) {
                        machine.name = hostname;
                    });
        }

        // Called each time the clusters have loaded and the zones have loaded.
        // Only once both have loaded will this method add the first machine.
        function initMachine() {
            if(ClustersManager.isLoaded() && ZonesManager.isLoaded()) {
                $scope.addMachine();
            }
        }

        // Load all of the architecture and keep then up-to-date.
        var loadArchitecturesPromise = null;
        function loadArchitectures(reload) {
            RegionConnection.callMethod("general.architectures", {}).then(
                function(arches) {
                    $scope.architectures = arches;

                    if(arches.length > 0) {
                        // If the currentMachine doesn't have an architecture
                        // set then it was created before all of the
                        // architectures were loaded. Set the default
                        // architecture for that machine.
                        if(angular.isObject($scope.currentMachine) &&
                            $scope.currentMachine.architecture === '') {
                            $scope.currentMachine.architecture =
                                defaultArchitecture();
                        }
                    }

                    if(arches.length === 0) {
                        // No architecture, so no boot images. Update every
                        // 3 seconds.
                        loadArchitecturesPromise = $timeout(
                            function() {
                                loadArchitectures(reload);
                            }, 3000);
                    } else if(reload) {
                        // Reload enabled, update every 10 seconds.
                        loadArchitecturesPromise = $timeout(
                            function() {
                                loadArchitectures(reload);
                            }, 10000);
                    }
                }, function() {
                    // Failed to load the architectures, try again in 3 sconds.
                    loadArchitecturesPromise = $timeout(
                        function() {
                            loadArchitectures(reload);
                        }, 3000);
                });
        }

        // Stop keeping the architectures up-to-date.
        function cancelLoadArchitectures() {
            if(angular.isObject(loadArchitecturesPromise)) {
                $timeout.cancel(loadArchitecturesPromise);
                loadArchitecturesPromise = null;
            }
        }

        // Converts the machine information from how it is held in the UI to
        // how it is handled over the websocket.
        function convertMachineToProtocol(machine) {
            // Convert the mac addresses.
            var macs = angular.copy(machine.macs);
            var pxe_mac = macs.shift().mac;
            var extra_macs = macs.map(function(mac) { return mac.mac; });

            // Return the new object.
            return {
                hostname: machine.name,
                architecture: machine.architecture,
                pxe_mac: pxe_mac,
                extra_macs: extra_macs,
                power_type: machine.power.type.name,
                power_parameters: angular.copy(machine.power.parameters),
                zone: {
                    id: machine.zone.id,
                    name: machine.zone.name
                },
                nodegroup: {
                    id: machine.cluster.id,
                    uuid: machine.cluster.uuid,
                    cluster_name: machine.cluster.cluster_name
                }
            };
        }

        // Called by the parent scope when this controller is viewable.
        $scope.show = function() {
            $scope.viewable = true;

            // Start the loading of architectures.
            loadArchitectures(true);

            // Update the currentMachine's hostname. This is to make sure
            // it is not already a hostname that has been taken. This just
            // helps reduce the chance of race conditions.
            return setRandomHostname($scope.currentMachine);
        };

        // Called by the parent scope when this controller is hidden.
        $scope.hide = function() {
            $scope.viewable = false;

            // Stop the loading of architectures.
            cancelLoadArchitectures();
        };

        // Add a new MAC address to the current machine.
        $scope.addMac = function() {
            $scope.currentMachine.macs.push(newMAC());
        };

        // Add a new machine and set it as the current selection.
        $scope.addMachine = function() {
            var machine = newMachine();
            $scope.machines.push(machine);
            $scope.currentMachine = machine;
            return setRandomHostname(machine);
        };

        // Change the current machine.
        $scope.setCurrentMachine = function(machine) {
            $scope.currentMachine = machine;
        };

        // Validate that the mac address is valid.
        $scope.validateMac = function(mac) {
            if(mac.mac === '') {
                mac.error = false;
            } else {
                mac.error = !$scope.macPattern.test(mac.mac);
            }
        };

        // Return true when the machine is missing information or invalid
        // information.
        $scope.hasError = function(machine) {
            // Early-out for errors.
            in_error = (
                machine.cluster === null ||
                machine.zone === null ||
                machine.architecture === '' ||
                machine.power.type === null);
            if(in_error) {
                return in_error;
            }

            // Make sure none of the mac addresses are in error. The first one
            // cannot be blank the remaining are allowed to be empty.
            if(machine.macs[0].mac === '' || machine.macs[0].error) {
                return true;
            }
            var i;
            for(i = 1; i < machine.macs.length; i++) {
                var mac = machine.macs[i];
                if(mac.mac !== '' && mac.error) {
                    return true;
                }
            }
            return false;
        };

        // Return true if any of the machines have errors.
        $scope.hasErrors = function() {
            for(i = 0; i < $scope.machines.length; i++) {
                if($scope.hasError($scope.machines[i])) {
                    return true;
                }
            }
            return false;
        };

        // Get the MAC address that is displayed in the machines header.
        $scope.getDisplayMac = function(machine) {
            if(machine.macs[0].mac === '') {
                return "00:00:00:00:00:00";
            } else {
                return machine.macs[0].mac;
            }
        };

        // Get the name of the power controller for the node.
        $scope.getDisplayPower = function(machine) {
            if(angular.isObject(machine.power.type)) {
                return machine.power.type.description;
            }
            return "Missing power type";
        };

        // Called when the add hardware action is cancelled.
        $scope.actionCancel = function() {
            $scope.currentMachine = null;
            $scope.machines = [];
            $scope.addMachine();

            // Hide the controller.
            $scope.hide();
        };

        // Called to perform the adding of machines.
        $scope.actionAdd = function() {
            // Does nothing if any error exists.
            if($scope.hasErrors()) {
                return;
            }

            // Get the current machines and clear the current view.
            var machines = $scope.machines;
            $scope.currentMachine = null;
            $scope.machines = [];
            $scope.addMachine();

            // Add all the machines.
            angular.forEach(machines, function(machine) {
                machine = convertMachineToProtocol(machine);
                NodesManager.create(machine).then(null, function(error) {
                    // This needs to be improved to show a correct error
                    // message on the machines line.
                    console.log(error);
                });
            });

            // Hide the controller.
            $scope.hide();
        };

        // Make sure connected to region then load all the clusters and zones.
        RegionConnection.defaultConnect().then(function() {
            if(!ClustersManager.isLoaded()) {
                // Load the initial clusters.
                ClustersManager.loadItems().then(function() {
                    initMachine();
                }, function(error) {
                    // Report error loading. This is simple handlng for now
                    // but this should show a nice error dialog or something.
                    console.log(error);
                });
            }
            ClustersManager.enableAutoReload();

            if(!ZonesManager.isLoaded()) {
                // Load the initial zones.
                ZonesManager.loadItems().then(function() {
                    initMachine();
                }, function(error) {
                    // Report error loading. This is simple handlng for now
                    // but this should show a nice error dialog or something.
                    console.log(error);
                });
            }
            ZonesManager.enableAutoReload();

            // Load all of the architectures.
            loadArchitectures(false);
        });
    }]);
