/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * OS/Release select directive.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject the os-select.html into the template cache.
    $templateCache.put('directive/templates/os-select.html', [
        '<select name="os" data-ng-model="ngModel.osystem" ',
            'data-ng-change="selectedOSChanged()" ',
            'data-ng-options="',
            'os[0] as os[1] for os in maasOsSelect.osystems">',
        '</select>',
        '<select name="release" data-ng-model="ngModel.release" ',
            'data-ng-options="',
            'release[0] as release[1] for release in releases">',
        '</select>'
    ].join(''));
}]);

angular.module('MAAS').directive('maasOsSelect', function() {
    return {
        restrict: "A",
        require: "ngModel",
        scope: {
            maasOsSelect: '=',
            ngModel: '='
        },
        templateUrl: 'directive/templates/os-select.html',
        controller: function($scope) {

            // Return only the selectable releases based on the selected os.
            function getSelectableReleases() {
                if(angular.isObject($scope.maasOsSelect)) {
                    var i, allChoices = $scope.maasOsSelect.releases;
                    var choice, choices = [];
                    for(i = 0; i < allChoices.length; i++) {
                        choice = allChoices[i];
                        if($scope.ngModel.osystem === "" && choice[0] === "") {
                            choices.push(choice);
                        } else if($scope.ngModel.osystem !== "" &&
                            choice[0].indexOf($scope.ngModel.osystem) > -1) {
                            choices.push(choice);
                        }
                    }
                    return choices;
                }
                return [];
            }

            // Defaults
            if(!angular.isObject($scope.ngModel)) {
                $scope.ngModel = {
                    osystem: "",
                    release: ""
                };
            }
            $scope.releases = getSelectableReleases();

            // If the available os change update the available releases.
            $scope.$watch("maasOsSelect", function() {
                $scope.releases = getSelectableReleases();
            });

            // Updates the default and selectable releases.
            $scope.selectedOSChanged = function() {
                $scope.releases = getSelectableReleases();
                $scope.ngModel.release = null;
                if($scope.releases.length > 0) {
                    $scope.ngModel.release = $scope.releases[0][0];
                }
            };
        }
    };
});
