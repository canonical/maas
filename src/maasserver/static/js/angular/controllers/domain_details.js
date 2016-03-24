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
        $scope.predicate = "name";
        $scope.reverse = false;

        // Updates the page title.
        function updateTitle() {
            if ($scope.isDefaultDomain()) {
                $rootScope.title = "Default domain " + $scope.domain.name;
            } else {
                $rootScope.title = $scope.domain.name;
            }
        }

        // Called when the domain has been loaded.
        function domainLoaded(domain) {
            $scope.domain = domain;
            if ($scope.isDefaultDomain()) {
                $scope.domain.displayname = $scope.domain.name + " (default)";
            } else {
                $scope.domain.displayname = $scope.domain.name;
            }
            $scope.loaded = true;

            updateTitle();
        }

        // Return true if the authenticated user is super user.
        $scope.isSuperUser = function() {
            return UsersManager.isSuperUser();
        };

        // Return true if this is the default domain.
        $scope.isDefaultDomain = function() {
            return $scope.domain.id === 0;
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
            $scope.confirmingDelete = true;
        };

        // Called when the cancel delete domain button is pressed.
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
                if (e instanceof SyntaxError) {
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

        // Called when the confirm delete domain button is pressed.
        $scope.deleteConfirmButton = function() {
            DomainsManager.deleteDomain($scope.domain).then(function() {
                $scope.confirmingDelete = false;
                $location.path("/domains");
            }, function(error) {
                $scope.error = $scope.convertPythonDictToErrorMsg(error);
            });
        };

        // Load all the required managers.
        ManagerHelperService.loadManagers([
            DomainsManager,
            UsersManager]).then(function() {
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
