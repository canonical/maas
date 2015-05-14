/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Add Device Controller
 */

angular.module('MAAS').controller('AddDeviceController', [
    '$scope', 'ClustersManager', 'DevicesManager', 'ManagerHelperService',
    'ValidationService', function($scope, ClustersManager, DevicesManager,
        ManagerHelperService, ValidationService) {

        // Set the addDeviceScope in the parent, so it can call functions
        // in this controller.
        var parentScope = $scope.$parent;
        parentScope.addDeviceScope = $scope;

        // Set initial values.
        $scope.viewable = false;
        $scope.clusters = ClustersManager.getItems();
        $scope.error = null;

        // Device ip assignment options.
        $scope.ipAssignments = [
            {
                name: "external",
                title: "External"
            },
            {
                name: "dynamic",
                title: "Dynamic"
            },
            {
                name: "static",
                title: "Static"
            }
        ];

        // Makes a new device.
        function makeDevice() {
            return {
                name: "",
                mac: "",
                ipAssignment: null,
                clusterInterfaceId: null,
                ipAddress: ""
            };
        }

        // Initial device.
        $scope.device = makeDevice();

        // Converts the device information from how it is held in the UI to
        // how it is handled over the websocket.
        function convertDeviceToProtocol(device) {
            // Return the new object.
            return {
                hostname: device.name,
                primary_mac: device.mac,
                ip_assignment: device.ipAssignment.name,
                ip_address: device.ipAddress,
                "interface": device.clusterInterfaceId
            };
        }

        // Gets the cluster interface by id from the managed cluster
        // interfaces.
        function getInterfaceById(id) {
            var i, clusterInterfaces = $scope.getManagedInterfaces();
            for(i = 0; i < clusterInterfaces.length; i++) {
                if(clusterInterfaces[i].id === id) {
                    return clusterInterfaces[i];
                }
            }
            return null;
        }

        // Called by the parent scope when this controller is viewable.
        $scope.show = function() {
            // Exit early if already viewable.
            if($scope.viewable) {
                return;
            }
            $scope.device = makeDevice();
            $scope.viewable = true;
        };

        // Called by the parent scope when this controller is hidden.
        $scope.hide = function() {
            $scope.viewable = false;

            // Emit the hidden event.
            $scope.$emit('addDeviceHidden');
        };

        // Return all of the managed interfaces from the clusters.
        $scope.getManagedInterfaces = function() {
            var nics = [];
            angular.forEach($scope.clusters, function(cluster) {
                angular.forEach(cluster.interfaces, function(cInterface) {
                    if(cInterface.management > 0) {
                        nics.push(cInterface);
                    }
                });
            });
            return nics;
        };

        // Return text to show an interfaces static range.
        $scope.getInterfaceStaticRange = function(nic) {
            return nic.network + " (" +
                nic.static_range.low + " - " + nic.static_range.high + ")";
        };

        // Returns true if the name is in error.
        $scope.nameHasError = function() {
            // If the name is empty don't show error.
            if($scope.device.name.length === 0) {
                return false;
            }
            return !ValidationService.validateHostname($scope.device.name);
        };

        // Returns true if the MAC is in error.
        $scope.macHasError = function() {
            // If the MAC is empty don't show error.
            if($scope.device.mac.length === 0) {
                return false;
            }
            return !ValidationService.validateMAC($scope.device.mac);
        };

        // Returns true if the IP address is in error.
        $scope.ipHasError = function() {
            // If the IP is empty don't show error.
            if($scope.device.ipAddress.length === 0) {
                return false;
            }
            // If ip address is invalid, then exit early.
            if(!ValidationService.validateIP($scope.device.ipAddress)) {
                return true;
            }
            var i, inNetwork, managedInterfaces = $scope.getManagedInterfaces();
            if(angular.isObject($scope.device.ipAssignment)){
                if($scope.device.ipAssignment.name === "external") {
                    // External IP address cannot be within a managed interface
                    // on one of the clusters.
                    for(i = 0; i < managedInterfaces.length; i++) {
                        inNetwork = ValidationService.validateIPInNetwork(
                            $scope.device.ipAddress,
                            managedInterfaces[i].network);
                        if(inNetwork) {
                            return true;
                        }
                    }
                } else if($scope.device.ipAssignment.name === "static" &&
                    angular.isNumber($scope.device.clusterInterfaceId)) {
                    // Static IP address must be within the static range
                    // of the selected clusterInterface.
                    var clusterInterface = getInterfaceById(
                        $scope.device.clusterInterfaceId);
                    inNetwork = ValidationService.validateIPInNetwork(
                        $scope.device.ipAddress, clusterInterface.network);
                    var inDynamicRange = ValidationService.validateIPInRange(
                        $scope.device.ipAddress, clusterInterface.network,
                        clusterInterface.dynamic_range.low,
                        clusterInterface.dynamic_range.high);
                    if(!inNetwork || inDynamicRange) {
                        return true;
                    }
                }
            }
            return false;
        };

        // Return true when the device is missing information or invalid
        // information.
        $scope.deviceHasError = function() {
            // Early-out for errors.
            in_error = (
                $scope.device.name === '' ||
                $scope.device.mac === '' ||
                !angular.isObject($scope.device.ipAssignment) ||
                $scope.nameHasError() ||
                $scope.macHasError());
            if(in_error) {
                return in_error;
            }
            if($scope.device.ipAssignment.name === "external") {
                return $scope.device.ipAddress === '' || $scope.ipHasError();
            }
            if($scope.device.ipAssignment.name === "static") {
                return !angular.isNumber($scope.device.clusterInterfaceId) ||
                    $scope.ipHasError();
            }
            return false;
        };

        // Called when cancel clicked.
        $scope.cancel = function() {
            $scope.error = null;
            $scope.device = makeDevice();
            $scope.hide();
        };

        // Convert the Python dict error message to displayed message.
        $scope.convertPythonDictToErrorMsg = function(pythonError) {
            var elements = pythonError.match(/'([A-Za-z0-9 \.:_\-]+)'/g);
            var result = '', msg = '';
            for (k=0; k < elements.length; ++k) {
                if (elements.hasOwnProperty(k)) {
                    switch(elements[k]) {
                        case "'hostname'":
                            msg = elements[++k].replace(/'/g,'');
                            result += msg.replace(/^Node/,'Device') + '  ';
                            break;
                        case "'mac_addresses'":
                            msg = elements[++k].replace(/'/g,'');
                            result += msg + '  ';
                            break;
                        default:
                            result += elements[k].replace(/'/g,'');
                    }
                }
            }
            return result;
        };

        // Called when save is clicked.
        $scope.save = function(addAnother) {
            // Do nothing if device in error.
            if($scope.deviceHasError()) {
                return;
            }

            // Clear the error so it can be set again, if it fails to save
            // the device.
            $scope.error = null;

            // Create the device.
            var device = convertDeviceToProtocol($scope.device);
            DevicesManager.create(device).then(function(device) {
                $scope.device = makeDevice();
                if(!addAnother) {
                    // Hide the scope if not adding another.
                    $scope.hide();
                }
            }, function(error) {
                $scope.error = $scope.convertPythonDictToErrorMsg(error);
            });
        };

        // Load clusters to get the managed interfaces.
        ManagerHelperService.loadManager(ClustersManager);
    }]);
