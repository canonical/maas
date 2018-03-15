/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Login button for external authentication.
 */

angular.module('MAAS').factory('getBakery', function() {
    return function(visitPage) {
        return new Bakery(
            new WebHandler(),
            new BakeryStorage(localStorage, {}), {visitPage: visitPage});
    };
}).directive('externalLogin', ['$window', 'getBakery',
                               function($window, getBakery) {
    return {
        restrict: 'E',
        scope: {},
        template: [
            '<a target="_blank" class="p-button--positive"',
            '    href="{{ loginURL }}"',
            '    title="Login through {{ externalAuthURL }}">',
            '  Go to login page',
            '</a>',
            '<div id="login-error" class="p-form-validation__message"',
            '    ng-if="errorMessage">',
            '    <strong>Error:</strong> {{ errorMessage }}',
            '</div>',
        ].join(''),
        controller: function($scope, $rootScope, $element, $document) {
            $scope.errorMessage = '';
            $scope.loginURL = '#';
            $scope.externalAuthURL = $element.attr('auth-url');

            const visitPage = function(error) {
                $scope.$apply(function() {
                    $scope.loginURL =  error.Info.VisitURL;
                    $scope.errorMessage = '';
                });
            }
            const bakery = getBakery(visitPage);
            const nextPath = $element.attr('next-path');
            bakery.get(
                '/MAAS/accounts/discharge-request/',
                {'Accept': 'application/json',
                 'Content-Type': 'application/json'},
                function(error, response) {
                    if (response.currentTarget.status != 200) {
                        $scope.errorMessage = 'failure getting login token';
                    } else {
                        $window.location.replace(nextPath);
                    }
                });
        }
    };
}]);
