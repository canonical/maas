/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Module
 *
 * Initializes the MAAS module with its required dependencies and sets up
 * the interpolater to use '{$' and '$}' instead of '{{' and '}}' as this
 * conflicts with Django templates.
 */

angular.module('MAAS', ['ngRoute', 'ngCookies', 'ngTagsInput']).config(
    function($interpolateProvider, $routeProvider) {
        $interpolateProvider.startSymbol('{$');
        $interpolateProvider.endSymbol('$}');

        // Helper that wrappers the templateUrl to append the files version
        // to the path. Used to override client cache.
        function versionedPath(path) {
            return path + "?v=" + MAAS_config.files_version;
        }

        // Setup routes only for the index page, all remaining pages should
        // not use routes. Once all pages are converted to using Angular this
        // will go away. Causing the page to never have to reload.
        var href = angular.element("base").attr('href');
        var path = document.location.pathname;
        if(path[path.length - 1] !== '/') {
            path += '/';
        }
        if(path === href) {
            $routeProvider.
                when('/nodes', {
                    templateUrl: versionedPath(
                        'static/partials/nodes-list.html'),
                    controller: 'NodesListController'
                }).
                when('/node/:system_id/result/:filename', {
                    templateUrl: versionedPath(
                        'static/partials/node-result.html'),
                    controller: 'NodeResultController'
                }).
                when('/node/:system_id/events', {
                    templateUrl: versionedPath(
                        'static/partials/node-events.html'),
                    controller: 'NodeEventsController'
                }).
                when('/node/:type/:system_id', {
                    templateUrl: versionedPath(
                        'static/partials/node-details.html'),
                    controller: 'NodeDetailsController'
                }).
                when('/node/:system_id', {
                    templateUrl: versionedPath(
                        'static/partials/node-details.html'),
                    controller: 'NodeDetailsController'
                }).
                when('/domains', {
                    templateUrl: versionedPath(
                        'static/partials/domains-list.html'),
                    controller: 'DomainsListController'
                }).
                when('/domain/:domain_id', {
                    templateUrl: versionedPath(
                        'static/partials/domain-details.html'),
                    controller: 'DomainDetailsController'
                }).
                when('/space/:space_id', {
                    templateUrl: versionedPath(
                        'static/partials/space-details.html'),
                    controller: 'SpaceDetailsController'
                }).
                when('/fabric/:fabric_id', {
                    templateUrl: versionedPath(
                        'static/partials/fabric-details.html'),
                    controller: 'FabricDetailsController'
                }).
                when('/subnets', {
                    redirectTo: '/networks?by=fabric'
                }).
                when('/networks', {
                    templateUrl: versionedPath(
                        'static/partials/networks-list.html'),
                    controller: 'NetworksListController',
                    reloadOnSearch: false
                }).
                when('/subnet/:subnet_id', {
                    templateUrl: versionedPath(
                        'static/partials/subnet-details.html'),
                    controller: 'SubnetDetailsController'
                }).
                when('/vlan/:vlan_id', {
                    templateUrl: versionedPath(
                        'static/partials/vlan-details.html'),
                    controller: 'VLANDetailsController',
                    controllerAs: 'vlanDetails'
                }).
                when('/settings/:section', {
                    templateUrl: versionedPath(
                        'static/partials/settings.html'),
                    controller: 'SettingsController'
                }).
                otherwise({
                    redirectTo: '/nodes'
                });
        }
    });

// Send pageview to Google Anayltics when the route has changed.
angular.module('MAAS').run(['$rootScope',
    function ($rootScope) {
        window.ga = window.ga || function() {
            (window.ga.q = window.ga.q || []).push(arguments);
        };
        window.ga.l = +new Date();
        window.ga('create', 'UA-1018242-63', 'auto');
        $rootScope.$on('$routeChangeSuccess', function() {
            var path = window.location.pathname + window.location.hash;
            window.ga('send', 'pageview', path);
        });
    }]);
