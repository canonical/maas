/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Controller status icon. Used in the controllers listing on the nodes page.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject the controller-status.html into the template cache.
    $templateCache.put('directive/templates/controller-status.html', [
        '<span class="icon {$ serviceClass $} no-margin">',
        '</span>'
    ].join(''));
}]);

angular.module('MAAS').directive('maasControllerStatus', [
    "ControllersManager", "ServicesManager",
    function(ControllersManager, ServicesManager) {
        return {
            restrict: "A",
            scope: {
                controller: '=maasControllerStatus'
            },
            templateUrl: 'directive/templates/controller-status.html',
            controller: function($scope) {

                $scope.serviceClass = "unknown";
                $scope.services = ServicesManager.getItems();

                // Return the status class for the service.
                function getClass(service) {
                    if(service.status === "running") {
                        return "success";
                    } else if (service.status === "degraged") {
                        return "warning";
                    } else if (service.status === "dead") {
                        return "error";
                    } else {
                        return "unknown";
                    }
                }

                // Update the class based on status of the services on the
                // controller.
                function updateStatusClass() {
                    $scope.serviceClass = "unknown";
                    if(angular.isObject($scope.controller)) {
                        var services = ControllersManager.getServices(
                            $scope.controller);
                        if(services.length > 0) {
                            var classes = services.map(getClass);
                            if(classes.indexOf("error") !== -1) {
                                $scope.serviceClass = "error";
                            } else if(classes.indexOf("warning") !== -1) {
                                $scope.serviceClass = "warning";
                            } else {
                                $scope.serviceClass = "success";
                            }
                        }
                    }
                }

                // Watch the services array and the services on the controller,
                // if any changes then update the status.
                $scope.$watch("controller.service_ids", updateStatusClass);
                $scope.$watchCollection("services", updateStatusClass);

                // Update on creation.
                updateStatusClass();
            }
        };
    }]);
