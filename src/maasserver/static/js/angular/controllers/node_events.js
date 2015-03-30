/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Node Events Controller
 */

angular.module('MAAS').controller('NodeEventsController', [
    '$scope', '$rootScope', '$routeParams',
    'NodesManager', 'EventsManagerFactory', 'ManagerHelperService',
    'ErrorService', function($scope, $rootScope, $routeParams,
        NodesManager, EventsManagerFactory, ManagerHelperService,
        ErrorService) {

        // Events manager that is loaded once the node is loaded.
        var eventsManager = null;

        // Set the title and page.
        $rootScope.title = "Loading...";
        $rootScope.page = "nodes";

        // Initial values.
        $scope.loaded = false;
        $scope.node = null;
        $scope.events = [];
        $scope.eventsLoaded = false;
        $scope.days = 30;

        // Called once the node is loaded.
        function nodeLoaded(node) {
            $scope.node = node;
            $scope.loaded = true;

            // Get the events manager and load it.
            eventsManager = EventsManagerFactory.getManager(node.id);
            $scope.events = eventsManager.getItems();
            $scope.days = eventsManager.getMaximumDays();
            eventsManager.loadItems().then(function() {
                $scope.eventsLoaded = true;
            });

            // Update the title when the fqdn of the node changes.
            $scope.$watch("node.fqdn", function() {
                $rootScope.title = $scope.node.fqdn + " - events";
            });
        }

        // Return the nice text for the given event.
        $scope.getEventText = function(event) {
            var text = event.type.description;
            if(angular.isString(event.description) &&
                event.description.length > 0) {
                text += " - " + event.description;
            }
            return text;
        };

        // Called to load more events.
        $scope.loadMore = function() {
            $scope.days += 30;
            eventsManager.loadMaximumDays($scope.days);
        };

        // Load nodes manager.
        ManagerHelperService.loadManager(NodesManager).then(function() {
            // If redirected from the NodeDetailsController then the node
            // will already be active. No need to set it active again.
            var activeNode = NodesManager.getActiveItem();
            if(angular.isObject(activeNode) &&
                activeNode.system_id === $routeParams.system_id) {
                nodeLoaded(activeNode);
            } else {
                NodesManager.setActiveItem(
                    $routeParams.system_id).then(function(node) {
                        nodeLoaded(node);
                    }, function(error) {
                        ErrorService.raiseError(error);
                    });
            }
        });

        // Destory the events manager when the scope is destroyed. This is so
        // the client will not recieve any more notifications about events
        // for this node.
        $scope.$on("$destroy", function() {
            if(angular.isObject(eventsManager)) {
                eventsManager.destroy();
            }
        });
    }]);
