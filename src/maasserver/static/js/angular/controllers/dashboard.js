/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Dashboard Controller
 */

angular.module('MAAS').controller('DashboardController', [
    '$scope', '$rootScope', '$routeParams', '$location',
    'DiscoveriesManager', 'DomainsManager', 'MachinesManager',
    'DevicesManager', 'SubnetsManager', 'VLANsManager', 'ConfigsManager',
    'ManagerHelperService',
    function($scope, $rootScope, $routeParams, $location,
             DiscoveriesManager, DomainsManager, MachinesManager,
             DevicesManager, SubnetsManager, VLANsManager, ConfigsManager,
             ManagerHelperService) {

        // Default device IP options.
        var deviceIPOptions = [
            ['dynamic', 'Dynamic'],
            ['static', 'Static'],
            ['external', 'External']
        ];

        // Set title and page.
        $rootScope.title = "Dashboard";
        $rootScope.page = "dashboard";

        // Set initial values.
        $scope.loading = true;
        $scope.discoveredDevices = DiscoveriesManager.getItems();
        $scope.domains = DomainsManager.getItems();
        $scope.machines = MachinesManager.getItems();
        $scope.devices = DevicesManager.getItems();
        $scope.configManager = ConfigsManager;
        $scope.networkDiscovery = null;
        $scope.column = 'mac';
        $scope.selectedDevice = null;
        $scope.convertTo = null;

        // Proxy manager that the maas-obj-form directive uses to call the
        // correct method based on current type.
        $scope.proxyManager = {
            updateItem: function(params) {
                if($scope.convertTo.type === 'device') {
                    return DevicesManager.createItem(params);
                } else if($scope.convertTo.type === 'interface') {
                    return DevicesManager.createInterface(params);
                } else {
                    throw new Error("Unknown type: " + $scope.convertTo.type);
                }
            }
        };

        // Return the name name for the Discovery.
        $scope.getDiscoveryName = function(discovery) {
            if(discovery.hostname === null) {
                if(discovery.mac_organization === null) {
                    return 'unknown-' +
                        discovery.mac_address.replace(/\:/g, "-");
                }
                else {
                    return 'unknown-' + discovery.mac_organization + '-' +
                        discovery.mac_address.split(":").slice(3, 6).join("-");
                }
            }
            else {
                return discovery.hostname;
            }
        };

        // Get the name of the subnet from its ID.
        $scope.getSubnetName = function(subnetId) {
            var subnet = SubnetsManager.getItemFromList(subnetId);
            return SubnetsManager.getName(subnet);
        };

        // Get the name of the VLAN from its ID.
        $scope.getVLANName = function(vlanId) {
            var vlan = VLANsManager.getItemFromList(vlanId);
            return VLANsManager.getName(vlan);
        };

        // Sets selected device
        $scope.toggleSelected = function(deviceId) {
            if($scope.selectedDevice === deviceId) {
                $scope.selectedDevice = null;
            } else {
                var discovered = DiscoveriesManager.getItemFromList(deviceId);
                $scope.convertTo = {
                    type: 'device',
                    hostname: $scope.getDiscoveryName(discovered),
                    domain: DomainsManager.getDefaultDomain(),
                    parent: null,
                    ip_assignment: 'dynamic',
                    goTo: false,
                    saved: false,
                    deviceIPOptions: deviceIPOptions.filter(
                        function(option) {
                            // Filter the options to not include static if
                            // a subnet is not defined for this discovered
                            // item.
                            if(option[0] === 'static' &&
                                !angular.isNumber(discovered.subnet)) {
                                return false;
                            } else {
                                return true;
                            }
                        })
                };
                $scope.selectedDevice = deviceId;
            }
        };

        // Called before the createItem is called to adjust the values
        // passed over the call.
        $scope.preProcess = function(item) {
            var discovered = DiscoveriesManager.getItemFromList(
                $scope.selectedDevice);
            item = angular.copy(item);
            if($scope.convertTo.type === 'device') {
                item.primary_mac = discovered.mac_address;
                item.extra_macs = [];
                item.interfaces = [{
                    mac: discovered.mac_address,
                    ip_assignment: item.ip_assignment,
                    ip_address: discovered.ip,
                    subnet: discovered.subnet
                }];
            } else if($scope.convertTo.type === 'interface') {
                item.mac_address = discovered.mac_address;
                item.ip_address = discovered.ip;
                item.subnet = discovered.subnet;
            }
            return item;
        };

        // Called after the createItem has been successful.
        $scope.afterSave = function(obj) {
            DiscoveriesManager._removeItem($scope.selectedDevice);
            $scope.selectedDevice = null;
            $scope.convertTo.hostname = obj.hostname;
            $scope.convertTo.parent = obj.parent;
            $scope.convertTo.saved = true;
            if($scope.convertTo.goTo) {
                if(angular.isString(obj.parent)) {
                    $location.path('/node/' + obj.parent);
                } else {
                    $location.path('/nodes').search({tab: 'devices'});
                }
            }
        };

        // Load all the managers and get the network discovery config item.
        ManagerHelperService.loadManagers($scope, [
            DiscoveriesManager, DomainsManager, MachinesManager,
            DevicesManager, SubnetsManager, VLANsManager, ConfigsManager]).then(
            function() {
                $scope.loading = false;
                $scope.networkDiscovery = ConfigsManager.getItemFromList(
                    'network_discovery');
            });
    }
]);
