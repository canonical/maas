/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Type directive.
 */

angular.module('MAAS').directive('ngType', function() {
    return {
        restrict: "A",
        scope: {
            ngType: "="
        },
        link: function(scope, element, attrs) {
            scope.$watch('ngType', function() {
                valid_types = [
                    'button',
                    'checkbox',
                    'color',
                    'date ',
                    'datetime ',
                    'datetime-local ',
                    'email ',
                    'file',
                    'hidden',
                    'image',
                    'month ',
                    'number ',
                    'password',
                    'radio',
                    'range ',
                    'reset',
                    'search',
                    'submit',
                    'tel',
                    'text',
                    'time ',
                    'url',
                    'week'
                ];
                if(valid_types.indexOf(scope.ngType) !== -1) {
                    element[0].type = scope.ngType;
                }
                else {
                    throw new Error("Invalid input type: " + scope.ngType);
                }

            });
        }
    };
});