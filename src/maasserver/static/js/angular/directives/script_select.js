/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Script select directive.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject the script-select.html into the template cache.
    $templateCache.put('directive/templates/script-select.html', [
        '<tags-input data-ng-model="ngModel" placeholder="Select scripts" ',
                'key-property="id" display-property="name" min-length=1',
                'on-tag-adding="onTagAdding($tag)" spellcheck="false"',
                'add-from-autocomplete-only="true" on-tag-removed="refocus()"',
                'on-tag-adding="onTagAdding($tag)" on-tag-added="refocus()">',
            '<auto-complete source="getScripts($query)" min-length="0" ',
                    'load-on-down-arrow="true" load-on-focus="true" ',
                    'load-on-empty="true" template="script-template" ',
                    'max-results-to-show="1000">',
            '</auto-complete>',
        '</tags-input>',
        '<script type="text/ng-template" id="script-template">',
            '<div>',
                '<p>',
                    '{{data.name}} {{data.tags_string}}',
                '</p>',
                '<span class="p-form-help-text">',
                    '{{data.description}}',
                '</span>',
            '</div>',
        '</script>'
    ].join(''));
}]);

angular.module('MAAS').directive(
        'maasScriptSelect',
        ['$q', 'ScriptsManager', 'ManagerHelperService',
        function($q, ScriptsManager, ManagerHelperService) {
    return {
        restrict: "A",
        require: "ngModel",
        scope: {
            ngModel: '=',
            scriptType: '='
        },
        templateUrl: 'directive/templates/script-select.html',
        link: function($scope, element, attrs, ngModelCtrl) {

            $scope.allScripts = ScriptsManager.getItems();
            $scope.scripts = [];
            $scope.getScripts = function(query) {
                $scope.scripts.length = 0;
                angular.forEach($scope.allScripts, function(script) {
                    if(script.script_type === $scope.scriptType &&
                            script.name.indexOf(query) >= 0) {
                        script.tags_string = '';
                        angular.forEach(script.tags, function (tag) {
                            if(script.tags_string === '') {
                                script.tags_string = '(' + tag;
                            } else {
                                script.tags_string += ', ' + tag;
                            }
                        });
                        if(script.tags_string !== '') {
                            script.tags_string += ')';
                        }
                        $scope.scripts.push(script);
                    }
                });
                return {
                    data: $scope.scripts
                };
            };
            $scope.onTagAdding = function(tag) {
                return tag.id !== undefined;
            };

            $scope.refocus = function() {
                var tagsInput = element.find('tags-input');
                var tagsInputScope = tagsInput.isolateScope();
                tagsInputScope.eventHandlers.input.change('');
                tagsInputScope.eventHandlers.input.focus();
                tagsInput.find('input').focus();
            };

            if(!angular.isArray($scope.ngModel)) {
                $scope.ngModel = [];
            }
            ManagerHelperService.loadManager($scope, ScriptsManager).then(
                function() {
                    $scope.ngModel.length = 0;
                    angular.forEach($scope.allScripts, function(script) {
                        if(script.script_type === $scope.scriptType &&
                           script.for_hardware.length === 0) {
                            if($scope.scriptType === 0) {
                                // By default MAAS runs all custom
                                // commissioning scripts in addition to all
                                // builtin commissioning scripts.
                                $scope.ngModel.push(script);
                            } else if($scope.scriptType === 2 &&
                                    script.tags.indexOf('commissioning') >= 0) {
                                // By default MAAS runs testing scripts which
                                // have been tagged 'commissioning'
                                $scope.ngModel.push(script);
                            }
                        }
                    });
                }
            );
        }
    };
}]);
