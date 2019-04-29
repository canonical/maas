/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Script runtime counter directive.
 */

/* @ngInject */
export function cacheScriptRuntime($templateCache) {
  // Inject the script_runtime.html into the template cache.
  $templateCache.put(
    "directive/templates/script_runtime.html",
    [
      '<span data-ng-if="(scriptStatus === 1 || scriptStatus === 7) &&',
      " estimatedRunTime !== 'Unknown'" + '">{{counter}} of ',
      "~{{estimatedRunTime}}</span>",
      '<span data-ng-if="(scriptStatus === 1 || scriptStatus === 7) &&',
      " estimatedRunTime == 'Unknown'" + '">{{counter}}</span>',
      '<span data-ng-if="scriptStatus === 0 && estimatedRunTime !== ',
      "'Unknown'" + '">~{{estimatedRunTime}}</span>',
      '<span data-ng-if="scriptStatus !== 0 && scriptStatus !== 1 ',
      '&& scriptStatus !== 7">{{runTime}}</span>'
    ].join("")
  );
}

export function maasScriptRunTime() {
  return {
    restrict: "A",
    require: ["startTime", "runTime", "estimatedRunTime", "scriptStatus"],
    scope: {
      startTime: "=",
      runTime: "@",
      estimatedRunTime: "@",
      scriptStatus: "="
    },
    templateUrl: "directive/templates/script_runtime.html",
    controller: ScriptRunTimeController
  };

  /* @ngInject */
  function ScriptRunTimeController($scope, $interval) {
    $scope.counter = "0:00:00";

    function incrementCounter() {
      if (
        ($scope.scriptStatus === 1 || $scope.scriptStatus === 7) &&
        $scope.startTime
      ) {
        var seconds = Math.floor(Date.now() / 1000 - $scope.startTime);
        var minutes = Math.floor(seconds / 60);
        var hours = Math.floor(minutes / 60);
        var days = Math.floor(hours / 24);
        hours = hours - days * 24;
        minutes = minutes - days * 24 * 60 - hours * 60;
        seconds =
          seconds - days * 24 * 60 * 60 - hours * 60 * 60 - minutes * 60;
        var new_counter = "";
        // This outputs the same format used by Python. It is
        // import to use the same format as when scripts are not
        // running runtime is taken from the region using Python's
        // format.
        if (days === 1) {
          new_counter = days + " day, ";
        } else if (days > 1) {
          new_counter = days + " days, ";
        }
        new_counter += hours + ":";
        if (minutes < 10) {
          new_counter += "0" + minutes + ":";
        } else {
          new_counter += minutes + ":";
        }
        if (seconds < 10) {
          new_counter += "0" + seconds;
        } else {
          new_counter += seconds;
        }
        $scope.counter = new_counter;
      }
    }

    // Update the counter on init, start the interval and stop it when
    // the directive is destroyed.
    incrementCounter();
    var promise = $interval(incrementCounter, 1000);
    $scope.$on("$destroy", function() {
      $interval.cancel(promise);
    });
  }
}
