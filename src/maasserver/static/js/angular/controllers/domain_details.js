/* Copyright 2015,2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Domain Details Controller
 */

angular.module('MAAS').controller('DomainDetailsController', [
    '$scope', '$rootScope', '$routeParams', '$location',
    'DomainsManager', 'ManagerHelperService', 'ErrorService',
    function(
        $scope, $rootScope, $routeParams, $location,
        DomainsManager, ManagerHelperService, ErrorService) {

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
            $rootScope.title = $scope.domain.name;
        }

        // Called when the domain has been loaded.
        function domainLoaded(domain) {
            $scope.domain = domain;
            $scope.loaded = true;

            updateTitle();
        }

        // Load all the required managers.
        ManagerHelperService.loadManager(DomainsManager).then(function() {
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
                    requestedDomain).then(function(node) {
                        domainLoaded(node);
                    }, function(error) {
                        ErrorService.raiseError(error);
                    });
            }
        });
    }]);
