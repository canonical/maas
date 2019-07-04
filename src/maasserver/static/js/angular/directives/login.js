/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Login button for external authentication.
 */

import bakery from "macaroon-bakery";

export function getBakery() {
  return function(visitPage) {
    return new bakery.Bakery({
      storage: new bakery.BakeryStorage(localStorage, {}),
      visitPage: visitPage
    });
  };
}

/* @ngInject */
export function externalLogin($window, getBakery) {
  return {
    restrict: "E",
    scope: {},
    template: [
      '<a target="_blank" class="p-button--positive"',
      '    href="{{ loginURL }}"',
      '    title="Login through {{ externalAuthURL }}">',
      "  Go to login page",
      "</a>",
      '<div id="login-error" class="p-form-validation__message"',
      '    ng-if="errorMessage">',
      "  <strong>Error getting login link:</strong><br>",
      "  {{ errorMessage }}",
      "</div>"
    ].join(""),
    controller: ExternalLoginController
  };

  /* @ngInject */
  function ExternalLoginController($scope, $element) {
    $scope.errorMessage = "";
    $scope.loginURL = "#";
    $scope.externalAuthURL = $element.attr("auth-url");

    const visitPage = function(error) {
      $scope.$apply(function() {
        $scope.loginURL = error.Info.VisitURL;
        $scope.errorMessage = "";
      });
    };
    const bakery = getBakery(visitPage);
    const nextPath = $element.attr("next-path");
    bakery.get(
      "/MAAS/accounts/discharge-request/",
      {
        Accept: "application/json",
        "Content-Type": "application/json"
      },
      function(error, response) {
        if (response.currentTarget.status != 200) {
          $scope.$apply(function() {
            $scope.errorMessage = response.currentTarget.responseText;
          });
          localStorage.clear();
        } else {
          $window.location.replace(nextPath);
        }
      }
    );
  }
}
