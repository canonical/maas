/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Add Hardware Controller
 */

angular.module('MAAS').controller('AddHardwareController', [
    '$scope', '$http', 'ClustersManager', 'ZonesManager',
    'NodesManager', 'GeneralManager', 'RegionConnection',
    'ManagerHelperService', 'ValidationService', function(
        $scope, $http, ClustersManager, ZonesManager, NodesManager,
        GeneralManager, RegionConnection, ManagerHelperService,
        ValidationService) {

        // Set the addHardwareScope in the parent, so it can call functions
        // in this controller.
        var parentScope = $scope.$parent;
        parentScope.addHardwareScope = $scope;

        // Set initial values.
        $scope.viewable = false;
        $scope.model = 'hardware';
        $scope.clusters = ClustersManager.getItems();
        $scope.zones = ZonesManager.getItems();
        $scope.architectures = GeneralManager.getData("architectures");

        // Input values.
        $scope.machines = [];
        $scope.currentMachine = null;
        $scope.chassis = null;

        // Hard coded chassis types. This is because there is no method in
        // MAAS to get a full list of supported chassis. This needs to be
        // fixed ASAP.
        var virshFields = [
            {
                name: 'power_address',
                label: 'Address',
                field_type: 'string',
                "default": '',  // Using "default" to make lint happy.
                choices: [],
                required: true
            },
            {
                name: 'power_pass',
                label: 'Password',
                field_type: 'string',
                "default": '',
                choices: [],
                required: true
            },
            {
                name: 'prefix_filter',
                label: 'Prefix filter',
                field_type: 'string',
                "default": '',
                choices: [],
                required: false
            }
        ];
        $scope.chassisPowerTypes = [
            {
                name: 'mscm',
                description: 'Moonshot Chassis Manager',
                fields: [
                    {
                        name: 'host',
                        label: 'Host',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'username',
                        label: 'Username',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'password',
                        label: 'Password',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    }
                ]
            },
            {
                name: 'powerkvm',
                description: 'PowerKVM',
                fields: virshFields
            },
            {
                name: 'seamicro15k',
                description: 'SeaMicro 15000',
                fields: [
                    {
                        name: 'mac',
                        label: 'MAC',
                        field_type: 'mac_address',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'username',
                        label: 'Username',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'password',
                        label: 'Password',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'power_control',
                        label: 'Power Control',
                        field_type: 'choice',
                        "default": 'restapi2',
                        choices: [
                            ['restapi2', 'REST API V2.0'],
                            ['restapi', 'REST API V0.9'],
                            ['ipmi', 'IPMI']
                        ],
                        required: true
                    }
                ]
            },
            {
                name: 'ucsm',
                description: 'UCS Chassis Manager',
                fields: [
                    {
                        name: 'url',
                        label: 'URL',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'username',
                        label: 'Username',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'password',
                        label: 'Password',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    }
                ]
            },
            {
                name: 'virsh',
                description: 'Virsh (virtual systems)',
                fields: virshFields
            },
            {
                name: 'esxi',
                description: 'VMWare ESXi (virsh)',
                fields: [
                    {
                        name: 'address',
                        label: 'Address',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'username',
                        label: 'Username',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'password',
                        label: 'Password',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'prefix_filter',
                        label: 'Prefix filter',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: false
                    }
                ]
            },
            {
                name: 'vsphere',
                description: 'VMWare vSphere/ESX/ESXi (python-vmomi)',
                fields: [
                    {
                        name: 'host',
                        label: 'Host',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'username',
                        label: 'Username',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'password',
                        label: 'Password',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: true
                    },
                    {
                        name: 'prefix_filter',
                        label: 'Prefix filter',
                        field_type: 'string',
                        "default": '',
                        choices: [],
                        required: false
                    }
                ]
            }
        ];

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

        // Return a new chassis object.
        function newChassis() {
            return {
                cluster: masterCluster(),
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

        // Validate that all the parameters are there for the given power type.
        function powerParametersHasError(power_type, parameters) {
            var i;
            for(i = 0; i < power_type.fields.length; i++) {
                var field = power_type.fields[i];
                var value = parameters[field.name];
                if(field.required) {
                    if(angular.isUndefined(value) || value === '') {
                        return true;
                    }
                }
            }
            return false;
        }

        // Called by the parent scope when this controller is viewable.
        $scope.show = function(mode) {
            // Change the mode.
            if($scope.mode !== mode) {
                if($scope.mode === "hardware") {
                    $scope.machines = [];
                    $scope.currentMachine = null;
                    $scope.addMachine();
                } else if($scope.mode === "chassis") {
                    $scope.chassis = newChassis();
                }
                $scope.mode = mode;
            }

            // Exit early if alreayd viewable.
            if($scope.viewable) {
                return;
            }
            $scope.viewable = true;

            // Start the polling of architectures.
            GeneralManager.startPolling("architectures");

            // Update the currentMachine's hostname. This is to make sure
            // it is not already a hostname that has been taken. This just
            // helps reduce the chance of race conditions.
            return setRandomHostname($scope.currentMachine);
        };

        // Called by the parent scope when this controller is hidden.
        $scope.hide = function() {
            $scope.viewable = false;

            // Stop the polling of architectures.
            GeneralManager.stopPolling("architectures");

            // Emit the hidden event.
            $scope.$emit('addHardwareHidden');
        };

        // Return True when architectures loaded and in hardware mode.
        $scope.showMachines = function() {
            if($scope.architectures.length === 0) {
                return false;
            }
            return $scope.mode === "hardware";
        };

        // Return True when architectures loaded and in chassis mode.
        $scope.showChassis = function() {
            if($scope.architectures.length === 0) {
                return false;
            }
            return $scope.mode === "chassis";
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

        // Return true if the machines name is invalid.
        $scope.invalidName = function(machine) {
            // Not invalid if empty.
            if(machine.name.length === 0) {
                return false;
            }
            return !ValidationService.validateHostname(machine.name);
        };

        // Validate that the mac address is valid.
        $scope.validateMac = function(mac) {
            if(mac.mac === '') {
                mac.error = false;
            } else {
                mac.error = !ValidationService.validateMAC(mac.mac);
            }
        };

        // Return true when the machine is missing information or invalid
        // information.
        $scope.machineHasError = function(machine) {
            // Early-out for errors.
            in_error = (
                machine.cluster === null ||
                machine.zone === null ||
                machine.architecture === '' ||
                machine.power.type === null ||
                $scope.invalidName(machine));
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
        $scope.machinesHaveErrors = function() {
            for(i = 0; i < $scope.machines.length; i++) {
                if($scope.machineHasError($scope.machines[i])) {
                    return true;
                }
            }
            return false;
        };

        // Return true if the chassis has errors.
        $scope.chassisHasErrors = function() {
            // Early-out for errors.
            in_error = (
                $scope.chassis === null ||
                $scope.chassis.cluster === null ||
                $scope.chassis.power.type === null);
            if(in_error) {
                return in_error;
            }
            return powerParametersHasError(
                $scope.chassis.power.type, $scope.chassis.power.parameters);
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
            $scope.chassis = newChassis();

            // Hide the controller.
            $scope.hide();
        };

        // Called to perform the adding of machines.
        $scope.actionAddMachines = function() {
            // Does nothing if any error exists.
            if($scope.machinesHaveErrors()) {
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

        // Called to perform the adding of a chassis.
        $scope.actionAddChassis = function() {
            // Does nothing if error exists.
            if($scope.chassisHasErrors()) {
                return;
            }

            // Get the current chassis and clear the current info.
            var chassis = $scope.chassis;
            $scope.chassis = newChassis();

            // Create the parameters.
            var params = angular.copy(chassis.power.parameters);
            params.model = chassis.power.type.name;

            // Add the chassis. For now we use the API as the websocket doesn't
            // support probe and enlist.
            $http({
                method: 'POST',
                url: 'api/1.0/nodegroups/' +
                    chassis.cluster.uuid +
                    '/?op=probe_and_enlist_hardware',
                data: $.param(params),
                headers: {'Content-Type': 'application/x-www-form-urlencoded'}
            }).then(null, function(error) {
                // This needs to be improved to show a correct error
                // message on the machines line.
                console.log(error);
            });

            // Hide the controller.
            $scope.hide();
        };

        // Load clusters and zones. Once loaded create the first machine and
        // chassis.
        ManagerHelperService.loadManagers(
            [ClustersManager, ZonesManager]).then(function() {
                // Add the first machine and chassis.
                $scope.addMachine();
                $scope.chassis = newChassis();
            });

        // Load the general manager.
        ManagerHelperService.loadManager(GeneralManager).then(function() {
            if($scope.architectures.length > 0) {
                // If the currentMachine doesn't have an architecture
                // set then it was created before all of the
                // architectures were loaded. Set the default
                // architecture for that machine.
                if(angular.isObject($scope.currentMachine) &&
                    $scope.currentMachine.architecture === '') {
                    $scope.currentMachine.architecture = defaultArchitecture();
                }
            }
        });

        // Stop polling when the scope is destroyed.
        $scope.$on("$destroy", function() {
            GeneralManager.stopPolling("architectures");
        });
    }]);
