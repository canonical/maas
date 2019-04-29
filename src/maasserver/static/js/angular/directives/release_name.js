/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Release name.
 *
 * Converts the provided release name into the release title.
 */

/* @ngInject */
function maasReleaseName(GeneralManager) {
  return {
    restrict: "A",
    scope: {
      releaseName: "=maasReleaseName"
    },
    link: function(scope, element, attrs) {
      scope.osinfo = GeneralManager.getData("osinfo");

      // Gets the release name.
      var getName = function() {
        if (angular.isArray(scope.osinfo.releases)) {
          for (let i = 0; i < scope.osinfo.releases.length; i++) {
            var release = scope.osinfo.releases[i];
            if (release[0] === scope.releaseName) {
              return release[1];
            }
          }
        }
        return scope.releaseName;
      };

      // Sets the text inside the element.
      var setText = function() {
        element.text(getName());
      };

      // Update the text when the release name or osinfo changes.
      scope.$watch("releaseName", function() {
        setText();
      });
      scope.$watchCollection("osinfo.releases", function() {
        setText();
      });
    }
  };
}

export default maasReleaseName;
