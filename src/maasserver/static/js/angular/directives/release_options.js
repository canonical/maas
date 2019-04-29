/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Release options directive.
 */

/* @ngInject */
export function cacheReleaseOptions($templateCache) {
  // Inject the release-options.html into the template cache.
  $templateCache.put(
    "directive/templates/release-options.html",
    [
      '<ul class="p-inline-list--settings u-no-margin--top">',
      '<li class="p-inline-list__item">',
      '<input id="diskErase" ',
      'type="checkbox" data-ng-model="maasReleaseOptions.erase" ',
      'data-ng-disabled="globalOptions.erase" ',
      'data-ng-change="onEraseChange()">',
      '<label for="diskErase">',
      "Erase disks before releasing",
      "</label>",
      "</li>",
      '<li class="p-inline-list__item">',
      '<input id="secureErase" ',
      'type="checkbox" ',
      'data-ng-model="maasReleaseOptions.secureErase" ',
      'data-ng-disabled="!maasReleaseOptions.erase">',
      '<label for="secureErase">',
      "Use secure erase",
      "</label>",
      "</li>",
      '<li class="p-inline-list__item">',
      '<input id="quickErase" type="checkbox" ',
      'data-ng-model="maasReleaseOptions.quickErase" ',
      'data-ng-disabled="!maasReleaseOptions.erase">',
      '<label for="quickErase">',
      "Use quick erase (not secure)",
      "</label>",
      "</li>",
      "</ul>"
    ].join("")
  );
}

/* @ngInject */
export function maasReleaseOptions(GeneralManager) {
  return {
    restrict: "A",
    scope: {
      maasReleaseOptions: "="
    },
    templateUrl: "directive/templates/release-options.html",
    link: function(scope, element, attrs) {
      // On click of enabling erasing set the others to the
      // global default value.
      scope.onEraseChange = function() {
        if (scope.maasReleaseOptions.erase) {
          scope.maasReleaseOptions.secureErase =
            scope.globalOptions.secure_erase;
          scope.maasReleaseOptions.quickErase = scope.globalOptions.quick_erase;
        } else {
          scope.maasReleaseOptions.secureErase = false;
          scope.maasReleaseOptions.quickErase = false;
        }
      };

      // Watch the global options. Once set update the defaults
      // of maasReleaseOptions.
      scope.globalOptions = GeneralManager.getData("release_options");
      scope.$watch(
        "globalOptions",
        function() {
          if (angular.isDefined(scope.globalOptions.erase)) {
            // Set the initial defaults for the release options.
            scope.maasReleaseOptions.erase = scope.globalOptions.erase;
            scope.onEraseChange();
          }
        },
        true
      );
    }
  };
}
