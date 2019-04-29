/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Add Domain Controller
 */

/* @ngInject */
function AddDomainController(
  $scope,
  DomainsManager,
  ManagerHelperService,
  ValidationService
) {
  // Set the addDomainScope in the parent, so it can call functions
  // in this controller.
  var parentScope = $scope.$parent;
  parentScope.addDomainScope = $scope;

  // Set initial values.
  $scope.viewable = false;
  $scope.error = null;

  // Makes a new domain.
  function makeDomain() {
    return {
      name: "",
      authoritative: true
    };
  }

  // Initial domain.
  $scope.domain = makeDomain();

  // Converts the domain information from how it is held in the UI to
  // how it is handled over the websocket.  Since they're identical, we
  // just return a copy: some day, they might be different, so we retain
  // the function against that day.
  function convertDomainToProtocol(domain) {
    return angular.copy(domain);
  }

  // Called by the parent scope when this controller is viewable.
  $scope.show = function() {
    // Exit early if already viewable.
    if ($scope.viewable) {
      return;
    }
    $scope.domain = makeDomain();
    $scope.viewable = true;
  };

  // Called by the parent scope when this controller is hidden.
  $scope.hide = function() {
    $scope.viewable = false;

    // Emit the hidden event.
    $scope.$emit("addDomainHidden");
  };

  // Returns true if the name is in error.
  $scope.nameHasError = function() {
    // If the name is empty don't show error.
    if ($scope.domain.name.length === 0) {
      return false;
    }
    return !ValidationService.validateDomainName($scope.domain.name);
  };

  // Return true when the domain is missing information or invalid
  // information.
  $scope.domainHasError = function() {
    if ($scope.domain.name === "" || $scope.nameHasError()) {
      return true;
    }

    return false;
  };

  // Called when cancel clicked.
  $scope.cancel = function() {
    $scope.error = null;
    $scope.domain = makeDomain();
    $scope.hide();
  };

  // Called when save is clicked.
  $scope.save = function(addAnother) {
    // Do nothing if domain in error.
    if ($scope.domainHasError()) {
      return;
    }

    // Clear the error so it can be set again, if it fails to save
    // the domain.
    $scope.error = null;

    // Create the domain.
    var domain = convertDomainToProtocol($scope.domain);
    DomainsManager.create(domain).then(
      function() {
        $scope.domain = makeDomain();
        if (!addAnother) {
          // Hide the scope if not adding another.
          $scope.hide();
        }
      },
      function(error) {
        $scope.error = ManagerHelperService.parseValidationError(error);
      }
    );
  };
}

export default AddDomainController;
