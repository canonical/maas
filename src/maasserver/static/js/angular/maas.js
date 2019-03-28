/* Copyright 2015-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Module
 *
 * Initializes the MAAS module with its required dependencies and sets up
 * the interpolater to use '{$' and '$}' instead of '{{' and '}}' as this
 * conflicts with Django templates.
 */

angular.module('MAAS',
    ['ngRoute', 'ngCookies', 'ngSanitize', 'ngTagsInput', 'vs-repeat']).config(
        function ($interpolateProvider, $routeProvider, $httpProvider,
            $compileProvider, tagsInputConfigProvider) {
        // Disable debugInfo unless in a karma context.
        // Re-enable debugInfo in development by running
        // angular.reloadWithDebugInfo(); in the console.
        // See: https://docs.angularjs.org/guide/production#disabling-debug-data
        $compileProvider.debugInfoEnabled(!!window.__karma__);

        $interpolateProvider.startSymbol('{$');
        $interpolateProvider.endSymbol('$}');

        tagsInputConfigProvider
            .setDefaults('autoComplete', {
                minLength: 0
            });

        // Set the $httpProvider to send the csrftoken in the header of any
        // http request.
        $httpProvider.defaults.xsrfCookieName = 'csrftoken';
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken';

        // Batch http responses into digest cycles
        $httpProvider.useApplyAsync(true);

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
            var routes = $routeProvider.
                when('/intro', {
                    templateUrl: versionedPath(
                        'static/partials/intro.html'),
                    controller: 'IntroController'
                }).
                when('/intro/user', {
                    templateUrl: versionedPath(
                        'static/partials/intro-user.html'),
                    controller: 'IntroUserController'
                }).
                when('/machines', {
                    templateUrl: versionedPath(
                        'static/partials/nodes-list.html'),
                    controller: 'NodesListController'
                }).
                when('/machine/:system_id/:result_type/:id', {
                    templateUrl: versionedPath(
                        'static/partials/node-result.html'),
                    controller: 'NodeResultController'
                }).
                when('/machine/:system_id/events', {
                    templateUrl: versionedPath(
                        'static/partials/node-events.html'),
                    controller: 'NodeEventsController'
                }).
                when('/machine/:system_id', {
                    templateUrl: versionedPath(
                        'static/partials/node-details.html'),
                    controller: 'NodeDetailsController'
                }).
                when('/devices', {
                    templateUrl: versionedPath(
                        'static/partials/nodes-list.html'),
                    controller: 'NodesListController'
                }).
                when('/device/:system_id/:result_type/:id', {
                    templateUrl: versionedPath(
                        'static/partials/node-result.html'),
                    controller: 'NodeResultController'
                }).
                when('/device/:system_id/events', {
                    templateUrl: versionedPath(
                        'static/partials/node-events.html'),
                    controller: 'NodeEventsController'
                }).
                when('/device/:system_id', {
                    templateUrl: versionedPath(
                        'static/partials/node-details.html'),
                    controller: 'NodeDetailsController'
                }).
                when('/controllers', {
                    templateUrl: versionedPath(
                        'static/partials/nodes-list.html'),
                    controller: 'NodesListController'
                }).
                when('/controller/:system_id/:result_type/:id', {
                    templateUrl: versionedPath(
                        'static/partials/node-result.html'),
                    controller: 'NodeResultController'
                }).
                when('/controller/:system_id/events', {
                    templateUrl: versionedPath(
                        'static/partials/node-events.html'),
                    controller: 'NodeEventsController'
                }).
                when('/controller/:system_id', {
                    templateUrl: versionedPath(
                        'static/partials/node-details.html'),
                    controller: 'NodeDetailsController'
                }).
                when('/nodes', {
                    redirectTo: '/machines'
                }).
                when('/node/machine/:system_id', {
                    redirectTo: '/machine/:system_id'
                }).
                when('/node/machine/:system_id/:result_type/:id', {
                    redirectTo: '/machine/:system_id/:result_type/:id'
                }).
                when('/node/machine/:system_id/events', {
                    redirectTo: '/machine/:system_id/events'
                }).
                when('/node/device/:system_id', {
                    redirectTo: '/device/:system_id'
                }).
                when('/node/device/:system_id/:result_type/:id', {
                    redirectTo: '/device/:system_id/:result_type/:id'
                }).
                when('/node/device/:system_id/events', {
                    redirectTo: '/device/:system_id/events'
                }).
                when('/node/controller/:system_id', {
                    redirectTo: '/controller/:system_id'
                }).
                when('/node/controller/:system_id/:result_type/:id', {
                    redirectTo: '/controller/:system_id/:result_type/:id'
                }).
                when('/node/controller/:system_id/events', {
                    redirectTo: '/controller/:system_id/events'
                }).
                when('/pods', {
                    templateUrl: versionedPath(
                        'static/partials/pods-list.html'),
                    controller: 'PodsListController'
                }).
                when('/pod/:id', {
                    templateUrl: versionedPath(
                        'static/partials/pod-details.html'),
                    controller: 'PodDetailsController'
                }).
                when('/images', {
                    templateUrl: versionedPath(
                        'static/partials/images.html'),
                    controller: 'ImagesController'
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
                when('/zone/:zone_id', {
                    templateUrl: versionedPath(
                        'static/partials/zone-details.html'),
                    controller: 'ZoneDetailsController'
                }).
                when('/zones', {
                    templateUrl: versionedPath(
                        'static/partials/zones-list.html'),
                    controller: 'ZonesListController',
                    reloadOnSearch: false
                }).
                when('/pools', {
                    templateUrl: versionedPath(
                        'static/partials/nodes-list.html'),
                    controller: 'NodesListController'
                });
            if(MAAS_config.superuser) {
                // Only superuser's can access the dashboard at the moment.
                routes = routes.when('/dashboard', {
                    templateUrl: versionedPath(
                        'static/partials/dashboard.html'),
                    controller: 'DashboardController'
                });
            }
            routes = routes.otherwise({
                redirectTo: '/machines'
            });
        }
    });

// Force users to #/intro when it has not been completed.
angular.module('MAAS').run(['$rootScope', '$location',
    function ($rootScope, $location) {
        $rootScope.$on('$routeChangeStart', function(event, next, current) {
            if(!MAAS_config.completed_intro) {
                if(next.controller !== 'IntroController') {
                    $location.path('/intro');
                }
            } else if (!MAAS_config.user_completed_intro) {
                if(next.controller !== 'IntroUserController') {
                    $location.path('/intro/user');
                }
            }
        });
    }]);

// Send pageview to Google Anayltics when the route has changed.
angular.module('MAAS').run(['$rootScope',
    function ($rootScope) {
        window.ga = window.ga || function() {
            (window.ga.q = window.ga.q || []).push(arguments);
        };
        window.ga.l = +new Date();
        window.ga('create', 'UA-1018242-63', 'auto', {
          userId: MAAS_config.analytics_user_id
        });
        window.ga('set', 'dimension1', MAAS_config.version);
        window.ga('set', 'dimension2', MAAS_config.uuid);
        $rootScope.$on('$routeChangeSuccess', function() {
            var path = window.location.pathname + window.location.hash;
            window.ga('send', 'pageview', path);
        });
    }]);
