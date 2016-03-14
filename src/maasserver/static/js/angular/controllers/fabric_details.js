/* Copyright 2015,2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Fabric Details Controller
 */

angular.module('MAAS').controller('FabricDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$filter', '$location',
    'FabricsManager', 'VLANsManager', 'SubnetsManager', 'SpacesManager',
    'ControllersManager',
    'UsersManager', 'ManagerHelperService', 'ErrorService',
    function(
        $scope, $rootScope, $routeParams, $filter, $location,
        FabricsManager, VLANsManager, SubnetsManager, SpacesManager,
        ControllersManager,
        UsersManager, ManagerHelperService, ErrorService) {

        // Set title and page.
        $rootScope.title = "Loading...";

        // Note: this value must match the top-level tab, in order for
        // highlighting to occur properly.
        $rootScope.page = "fabrics";

        // Initial values.
        $scope.loaded = false;
        $scope.fabric = null;
        $scope.vlans = null;

        // Updates the page title.
        function updateTitle() {
            $rootScope.title = $scope.fabric.name;
        }

        // Called when the fabric has been loaded.
        function fabricLoaded(fabric) {
            $scope.fabric = fabric;
            $scope.loaded = true;
            $scope.vlans = FabricsManager.getVLANs($scope.fabric);
            $scope.racks = getRackControllers();

            updateTitle();
            updateVLANTable();
        }

        // Return the rack controller objects attached to this Fabric.  The
        // returned array is calculated on each call, you should not watch this
        // array, instead you should watch this function.
        function getRackControllers() {
            var racks = [];
            angular.forEach($scope.vlans, function(vlan) {
                angular.forEach(vlan.rack_sids, function(rack_sid) {
                    var rack = ControllersManager.getItemFromList(rack_sid);
                    if(angular.isObject(rack)) {
                        racks.push(rack);
                    }
                });
            });
            return racks;
        }

        // Generate a table that can easily be rendered in the view.
        function updateVLANTable() {
            var rows = [];
            var vlans = $filter('orderBy')($scope.vlans, ['name']);
            angular.forEach(vlans, function(vlan) {
                var subnets = $filter('orderBy')(
                    VLANsManager.getSubnets(vlan), ['cidr']);
                if(subnets.length > 0) {
                    angular.forEach(subnets, function(subnet) {
                        var space = SpacesManager.getItemFromList(
                            subnet.space);
                        var row = {
                            vlan: vlan,
                            vlan_name: VLANsManager.getName(vlan),
                            subnet: subnet,
                            subnet_name: SubnetsManager.getName(subnet),
                            space: space,
                            space_name: space.name
                        };
                        rows.push(row);
                    });
                }
            });
            $scope.rows = rows;
        }


        // Return true if the authenticated user is super user.
        $scope.isSuperUser = function() {
            return UsersManager.isSuperUser();
        };

        // Return true if this is the default Fabric
        $scope.isDefaultFabric = function() {
            if(!angular.isObject($scope.fabric)) {
                return false;
            }
            return $scope.fabric.id === 0;
        };

        // Called when the delete fabric button is pressed.
        $scope.deleteButton = function() {
            $scope.confirmingDelete = true;
        };

        // Called when the cancel delete fabric button is pressed.
        $scope.cancelDeleteButton = function() {
            $scope.confirmingDelete = false;
        };

        // Convert the Python dict error message to displayed message.
        // We know it's probably a form ValidationError dictionary, so just use
        // it as such, and recover if that doesn't parse as JSON.
        $scope.convertPythonDictToErrorMsg = function(pythonError) {
            var dictionary;
            try {
                dictionary = JSON.parse(pythonError);
            } catch(e) {
                if(e instanceof SyntaxError) {
                    return pythonError;
                } else {
                    throw e;
                }
            }
            var result = '', msg = '';
            var key;
            angular.forEach(dictionary, function(value, key) {
                result += key + ":  ";
                angular.forEach(dictionary[key], function(value) {
                        result += value + "  ";
                });
            });
            return result;
        };

        // Called when the confirm delete fabric button is pressed.
        $scope.deleteConfirmButton = function() {
            FabricsManager.deleteFabric($scope.fabric).then(function() {
                $scope.confirmingDelete = false;
                $location.path("/fabrics");
            }, function(error) {
                $scope.error = $scope.convertPythonDictToErrorMsg(error);
            });
        };

        // Load all the required managers.
        ManagerHelperService.loadManagers([
            FabricsManager, VLANsManager, SubnetsManager, SpacesManager,
            ControllersManager, UsersManager]).then(function() {
            // Possibly redirected from another controller that already had
            // this fabric set to active. Only call setActiveItem if not
            // already the activeItem.
            var activeFabric = FabricsManager.getActiveItem();
            var requestedFabric = parseInt($routeParams.fabric_id, 10);
            if(isNaN(requestedFabric)) {
                ErrorService.raiseError("Invalid fabric identifier.");
            } else if(angular.isObject(activeFabric) &&
                activeFabric.id === requestedFabric) {
                fabricLoaded(activeFabric);
            } else {
                FabricsManager.setActiveItem(
                    requestedFabric).then(function(fabric) {
                        fabricLoaded(fabric);
                    }, function(error) {
                        ErrorService.raiseError(error);
                    });
            }
        });
    }]);
