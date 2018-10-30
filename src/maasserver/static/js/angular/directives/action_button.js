/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Action button directive.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject action-button.html into the template cache.
    $templateCache.put('directive/templates/action-button.html', [
        '<button data-ng-transclude class="p-action-button" ',
            'data-ng-class="{ \'is-indeterminate\': indeterminateState, ',
            '\'is-done\': doneState }">',
        '</button>'
    ].join(''));
}]);

angular.module('MAAS').directive('maasActionButton', function() {
    return {
        restrict: "E",
        replace: true,
        transclude: true,
        scope: {
            doneState: '<',
            indeterminateState: '<',
        },
        templateUrl: 'directive/templates/action-button.html',
    };
});
