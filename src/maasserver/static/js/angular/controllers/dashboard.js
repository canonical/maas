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
        $scope.deviceManager = DevicesManager;
        $scope.configManager = ConfigsManager;
        $scope.networkDiscovery = null;
        $scope.column = 'mac';
        $scope.selectedDevice = null;
        $scope.convertTo = null;

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
                    ip_assignment: 'dynamic',
                    goTo: false,
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
            item.primary_mac = discovered.mac_address;
            item.extra_macs = [];
            item.interfaces = [{
                mac: discovered.mac_address,
                ip_assignment: item.ip_assignment,
                ip_address: discovered.ip,
                subnet: discovered.subnet
            }];
            return item;
        };

        // Called after the createItem has been successful.
        $scope.afterSave = function() {
            DiscoveriesManager._removeItem($scope.selectedDevice);
            $scope.selectedDevice = null;
            if($scope.convertTo.goTo) {
                $location.path('/nodes').search({tab: 'devices'});
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
