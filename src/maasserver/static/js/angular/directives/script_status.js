/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Script status icon select directive.
 */

function cacheScriptStatus($templateCache) {
    // Inject the script_status.html into the template cache.
    $templateCache.put('directive/templates/script_status.html', [
        '<span data-ng-class="icon" data-ng-show="show"></span>'
    ].join(''));
};

function maasScriptStatus() {
    return {
        restrict: "A",
        require: "scriptStatus",
        scope: {
            scriptStatus: '='
        },
        templateUrl: 'directive/templates/script_status.html',
        controller: function($scope) {
            function getIcon() {
                $scope.show = true;
                switch ($scope.scriptStatus) {
                    // SCRIPT_STATUS.PENDING
                    case 0:
                        $scope.icon = 'p-icon--pending';
                        break;
                    // SCRIPT_STATUS.RUNNING
                    case 1:
                    // SCRIPT_STATUS.INSTALLING
                    case 7:
                        $scope.icon = 'p-icon--running';
                        break;
                    // SCRIPT_STATUS.PASSED
                    case 2:
                        $scope.icon = 'p-icon--pass';
                        break;
                    // SCRIPT_STATUS.FAILED
                    case 3:
                    // SCRIPT_STATUS.ABORTED
                    case 5:
                    // SCRIPT_STATUS.DEGRADED
                    case 6:
                    // SCRIPT_STATUS.FAILED_INSTALLING
                    case 8:
                        $scope.icon = 'p-icon--error';
                        break;
                    // SCRIPT_STATUS.TIMEDOUT
                    case 4:
                        $scope.icon = 'p-icon--timed-out';
                        break;
                    // SCRIPT_STATUS.SKIPPED
                    case 9:
                        $scope.icon = 'p-icon--warning';
                        break;
                    case -1:
                        // No scripts have been run.
                        $scope.show = false;
                        break;
                    default:
                        $scope.icon = 'p-icon--help';
                        break;
                }
            }

            getIcon();

            $scope.$watch("scriptStatus", function() {
                getIcon();
            });
        }
    };
};

const maas = angular.module('MAAS');
maas.run(cacheScriptStatus);
maas.directive('maasScriptStatus', maasScriptStatus);
