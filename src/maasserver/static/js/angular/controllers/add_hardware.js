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
        $scope.model = 'machine';
        $scope.clusters = ClustersManager.getItems();
        $scope.zones = ZonesManager.getItems();
        $scope.architectures = GeneralManager.getData("architectures");
        $scope.error = null;

        // Input values.
        $scope.machine = null;
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
                name: 'vmware',
                description: 'VMWare',
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
        function newMachine(cloneMachine) {
            // Clone the machine instead of just creating a new one.
            // This helps the user by already having the previous selected
            // items selected for the new machine.
            if(angular.isObject(cloneMachine)) {
                return {
                    cluster: cloneMachine.cluster,
                    name: '',
                    macs: [newMAC()],
                    zone: cloneMachine.zone,
                    architecture: cloneMachine.architecture,
                    power: {
                        type: cloneMachine.power.type,
                        parameters: {}
                    }
                };
            }

            // No clone machine. So create a new blank machine.
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
                if($scope.mode === "machine") {
                    $scope.machine = newMachine();
                } else if($scope.mode === "chassis") {
                    $scope.chassis = newChassis();
                }
                $scope.error = null;
                $scope.mode = mode;
            }

            // Exit early if alreayd viewable.
            if($scope.viewable) {
                return;
            }
            $scope.viewable = true;

            // Start the polling of architectures.
            GeneralManager.startPolling("architectures");
        };

        // Called by the parent scope when this controller is hidden.
        $scope.hide = function() {
            $scope.viewable = false;

            // Stop the polling of architectures.
            GeneralManager.stopPolling("architectures");

            // Emit the hidden event.
            $scope.$emit('addHardwareHidden');
        };

        // Return True when architectures loaded and in machine mode.
        $scope.showMachine = function() {
            if($scope.architectures.length === 0) {
                return false;
            }
            return $scope.mode === "machine";
        };

        // Return True when architectures loaded and in chassis mode.
        $scope.showChassis = function() {
            if($scope.architectures.length === 0) {
                return false;
            }
            return $scope.mode === "chassis";
        };

        // Add a new MAC address to the machine.
        $scope.addMac = function() {
            $scope.machine.macs.push(newMAC());
        };

        // Return true if the machine name is invalid.
        $scope.invalidName = function() {
            // Not invalid if empty.
            if($scope.machine.name.length === 0) {
                return false;
            }
            return !ValidationService.validateHostname($scope.machine.name);
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
        $scope.machineHasError = function() {
            // Early-out for errors.
            in_error = (
                $scope.machine === null ||
                $scope.machine.cluster === null ||
                $scope.machine.zone === null ||
                $scope.machine.architecture === '' ||
                $scope.machine.power.type === null ||
                $scope.invalidName($scope.machine));
            if(in_error) {
                return in_error;
            }

            // Make sure none of the mac addresses are in error. The first one
            // cannot be blank the remaining are allowed to be empty.
            if($scope.machine.macs[0].mac === '' ||
                $scope.machine.macs[0].error) {
                return true;
            }
            var i;
            for(i = 1; i < $scope.machine.macs.length; i++) {
                var mac = $scope.machine.macs[i];
                if(mac.mac !== '' && mac.error) {
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

        // Called when the cancel button is pressed.
        $scope.cancel = function() {
            $scope.error = null;
            $scope.machine = newMachine();
            $scope.chassis = newChassis();

            // Hide the controller.
            $scope.hide();
        };

        // Called to perform the saving of the machine.
        $scope.saveMachine = function(addAnother) {
            // Does nothing if machine has errors.
            if($scope.machineHasError()) {
                return;
            }

            // Clear the error so it can be set again, if it fails to save
            // the device.
            $scope.error = null;

            // Add the machine.
            NodesManager.create(convertMachineToProtocol($scope.machine)).then(
                function() {
                    if(addAnother) {
                        $scope.machine = newMachine($scope.machine);
                    } else {
                        $scope.machine = newMachine();

                        // Hide the scope if not adding another.
                        $scope.hide();
                    }
                }, function(error) {
                    $scope.error = error;
                });
        };

        // Called to perform the saving of the chassis.
        $scope.saveChassis = function(addAnother) {
            // Does nothing if error exists.
            if($scope.chassisHasErrors()) {
                return;
            }

            // Clear the error so it can be set again, if it fails to save
            // the device.
            $scope.error = null;

            // Create the parameters.
            var params = angular.copy($scope.chassis.power.parameters);
            params.model = $scope.chassis.power.type.name;

            // Add the chassis. For now we use the API as the websocket doesn't
            // support probe and enlist.
            $http({
                method: 'POST',
                url: 'api/1.0/nodegroups/' +
                    $scope.chassis.cluster.uuid +
                    '/?op=probe_and_enlist_hardware',
                data: $.param(params),
                headers: {'Content-Type': 'application/x-www-form-urlencoded'}
            }).then(function() {
                $scope.chassis = newChassis();
                if(!addAnother) {
                    // Hide the scope if not adding another.
                    $scope.hide();
                }
            }, function(error) {
                $scope.error = error;
            });
        };

        // Load clusters and zones. Once loaded create the first machine and
        // chassis.
        ManagerHelperService.loadManagers(
            [ClustersManager, ZonesManager]).then(function() {
                // Add the first machine and chassis.
                $scope.machine = newMachine();
                $scope.chassis = newChassis();
            });

        // Load the general manager.
        ManagerHelperService.loadManager(GeneralManager).then(function() {
            if($scope.architectures.length > 0) {
                // If the machine doesn't have an architecture
                // set then it was created before all of the
                // architectures were loaded. Set the default
                // architecture for that machine.
                if(angular.isObject($scope.machine) &&
                    $scope.machine.architecture === '') {
                    $scope.machine.architecture = defaultArchitecture();
                }
            }
        });

        // Stop polling when the scope is destroyed.
        $scope.$on("$destroy", function() {
            GeneralManager.stopPolling("architectures");
        });
    }]);
