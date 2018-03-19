/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Domain Details Controller
 */

angular.module('MAAS').controller('DomainDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$location',
    'DomainsManager', 'UsersManager', 'ManagerHelperService', 'ErrorService',
    function(
        $scope, $rootScope, $routeParams, $location,
        DomainsManager, UsersManager, ManagerHelperService, ErrorService) {

        // Set title and page.
        $rootScope.title = "Loading...";

        // Note: this value must match the top-level tab, in order for
        // highlighting to occur properly.
        $rootScope.page = "domains";

        // Initial values.
        $scope.loaded = false;
        $scope.domain = null;
        $scope.editSummary = false;
        $scope.predicate = "name";
        $scope.reverse = false;
        $scope.action = null;

        $scope.domainsManager = DomainsManager;
        $scope.newObject = {};

        $scope.supportedRecordTypes = [
            'A', 'AAAA', 'CNAME', 'MX', 'NS', 'SRV', 'SSHFP', 'TXT'
        ];

        // Set default predicate to name.
        $scope.predicate = 'name';

        // Sorts the table by predicate.
        $scope.sortTable = function(predicate) {
            $scope.predicate = predicate;
            $scope.reverse = !$scope.reverse;
        };

        $scope.enterEditSummary = function() {
            $scope.editSummary = true;
        };

        // Called when the "cancel" button is clicked in the domain summary.
        $scope.exitEditSummary = function() {
            $scope.editSummary = false;
        };

        // Updates the page title.
        function updateTitle() {
            $rootScope.title = $scope.domain.displayname;
        }

        // Called when the domain has been loaded.
        function domainLoaded(domain) {
            $scope.domain = domain;
            $scope.loaded = true;

            updateTitle();
        }

        // Return true if the authenticated user is super user.
        $scope.isSuperUser = function() {
            return UsersManager.isSuperUser();
        };

        // Return true if this is the default domain.
        $scope.isDefaultDomain = function() {
            if(angular.isObject($scope.domain)) {
                return $scope.domain.id === 0;
            }
            return false;
        };

        // Called to check if the space can be deleted.
        $scope.canBeDeleted = function() {
            if(angular.isObject($scope.domain)) {
                return $scope.domain.rrsets.length === 0;
            }
            return false;
        };

        // Called when the delete domain button is pressed.
        $scope.deleteButton = function() {
            $scope.error = null;
            $scope.actionInProgress = true;
            $scope.action = 'delete';
        };

        // Called when the add record button is pressed.
        $scope.addRecordButton = function() {
            $scope.error = null;
            $scope.actionInProgress = true;
            $scope.action = 'add_record';
        };

        // Called when the cancel delete domain button is pressed.
        $scope.cancelAction = function() {
            $scope.actionInProgress = false;
        };

        // Called when the confirm delete domain button is pressed.
        $scope.deleteConfirmButton = function() {
            DomainsManager.deleteDomain($scope.domain).then(function() {
                $scope.actionInProgress = false;
                $location.path("/domains");
            }, function(error) {
                $scope.error =
                    ManagerHelperService.parseValidationError(error);
            });
        };

        // Load all the required managers.
        ManagerHelperService.loadManagers(
            $scope, [DomainsManager, UsersManager]).then(function() {
            // Possibly redirected from another controller that already had
            // this domain set to active. Only call setActiveItem if not
            // already the activeItem.
            var activeDomain = DomainsManager.getActiveItem();
            var requestedDomain = parseInt($routeParams.domain_id, 10);
            if(isNaN(requestedDomain)) {
                ErrorService.raiseError("Invalid domain identifier.");
            } else if(angular.isObject(activeDomain) &&
                activeDomain.id === requestedDomain) {
                domainLoaded(activeDomain);
            } else {
                DomainsManager.setActiveItem(
                    requestedDomain).then(function(domain) {
                        domainLoaded(domain);
                    }, function(error) {
                        ErrorService.raiseError(error);
                    });
            }
        });
    }]);
