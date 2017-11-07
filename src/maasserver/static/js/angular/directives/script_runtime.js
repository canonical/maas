/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Script runtime counter directive.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject the script_runtime.html into the template cache.
    $templateCache.put('directive/templates/script_runtime.html', [
        '<span data-ng-if="(scriptStatus === 1 || scriptStatus === 7) &&',
        " estimatedRunTime !== 'Unknown'" + '">{{counter}} of ',
        '~{{estimatedRunTime}}</span>',
        '<span data-ng-if="(scriptStatus === 1 || scriptStatus === 7) &&',
        " estimatedRunTime == 'Unknown'" + '">{{counter}}</span>',
        '<span data-ng-if="scriptStatus === 0 && estimatedRunTime !== ',
        "'Unknown'" + '">~{{estimatedRunTime}}</span>',
        '<span data-ng-if="scriptStatus !== 0 && scriptStatus !== 1 ',
        '&& scriptStatus !== 7">{{runTime}}</span>'
    ].join(''));
}]);

angular.module('MAAS').directive('maasScriptRunTime', function() {
    return {
        restrict: "A",
        require: ["startTime", "runTime", "estimatedRunTime", "scriptStatus"],
        scope: {
            startTime: '=',
            runTime: '@',
            estimatedRunTime: '@',
            scriptStatus: '='
        },
        templateUrl: 'directive/templates/script_runtime.html',
        controller: function($scope, $interval) {
            $scope.counter = "0:00:00";

            function incrementCounter() {
                if(($scope.scriptStatus === 1 || $scope.scriptStatus === 7) &&
                    $scope.startTime) {
                    var date = new Date(null);
                    date.setSeconds((Date.now()/1000) - $scope.startTime);
                    $scope.counter = date.toISOString().substr(11, 8);
                    if($scope.counter.indexOf('00:') === 0) {
                      $scope.counter = $scope.counter.substr(1);
                    }
                }
            }

            // Update the counter on init, start the interval and stop it when
            // the directive is destroyed.
            incrementCounter();
            var promise = $interval(incrementCounter, 1000);
            $scope.$on('$destroy', function() {
              $interval.cancel(promise);
            });
        }
    };
});
