/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Action button directive.
 */

function cacheActionButton($templateCache) {
    // Inject action-button.html into the template cache.
    $templateCache.put('directive/templates/action-button.html', [
        '<button data-ng-transclude class="p-action-button" ',
            'data-ng-class="{ \'is-indeterminate\': indeterminateState, ',
            '\'is-done\': doneState }">',
        '</button>'
    ].join(''));
};

function maasActionButton() {
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
};

const maas = angular.module('MAAS');
maas.run(cacheActionButton);
maas.directive('maasActionButton', maasActionButton);
