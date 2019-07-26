/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * User preferences MAAS key
 *
 * Provides the interactivity of the MAAS key section of the user profile.
 */

/* @ngInject */
export function maasPrefKeys($q, RegionConnection, UsersManager) {
  return {
    restrict: "A",
    controller: function() {
      var self = this;

      self.addKey = function() {
        var defer = $q.defer();
        RegionConnection.defaultConnect().then(function() {
          UsersManager.createAuthorisationToken().then(function(token) {
            if (self.injector) {
              self.injector(token);
            }
            defer.resolve(token);
          });
        });
        return defer.promise;
      };

      self.deleteKey = function(key) {
        RegionConnection.defaultConnect().then(function() {
          UsersManager.deleteAuthorisationToken(key);
        });
      };
    }
  };
}

/* @ngInject */
export function maasPrefKeysInject($compile, $templateCache) {
  return {
    restrict: "A",
    require: "^maasPrefKeys",
    scope: {
      template: "@maasPrefKeysInject"
    },
    link: function($scope, $element, $attrs, controller) {
      var template = $templateCache.get($scope.template);
      if (!template) {
        throw new Error("Unable to load template: " + $scope.template);
      }

      // Set the injector on the controller.
      controller.injector = function(token) {
        var newScope = $scope.$new();
        newScope.token = token;

        var newElement = angular.element(template);
        $element.append(newElement);
        $compile(newElement)(newScope);
      };
    }
  };
}

export function maasPrefKeysAdd() {
  return {
    restrict: "A",
    require: "^maasPrefKeys",
    link: function($scope, $element, $attrs, controller) {
      var spinner = '<i class="p-icon--spinner u-animation--spin"></i>';

      $element.on("click", function(evt) {
        evt.preventDefault();

        // Add the spinner.
        $scope.addingKey = true;
        var spinElement = angular.element(spinner);
        $element.prepend(spinElement);

        // Add the new key.
        $scope.$apply(function() {
          controller.addKey().then(function() {
            // Remove the spinner.
            $scope.addingKey = false;
            spinElement.remove();
          });
        });
      });
    }
  };
}

export function maasPrefKey() {
  return {
    restrict: "A",
    require: "^maasPrefKeys",
    scope: {
      key: "@maasPrefKey"
    },
    controller: DeleteKey,
    link: function($scope, $element, $attrs, controller) {
      // Needed so the controller of this directive can get the parent
      // controller.
      $scope.prefsController = controller;
    }
  };

  /* @ngInject */
  function DeleteKey($scope, $element) {
    var self = this;

    self.deleteKey = function() {
      $scope.prefsController.deleteKey($scope.key);

      // Delete self.
      $scope.$destroy();
      $element.remove();
    };
  }
}

export function maasPrefKeyDelete() {
  return {
    restrict: "A",
    require: "^maasPrefKey",
    link: function($scope, $element, $attrs, controller) {
      $element.on("click", function(evt) {
        evt.preventDefault();

        $scope.$apply(function() {
          controller.deleteKey();
        });
      });
    }
  };
}

export function maasPrefKeyCopy() {
  return {
    restrict: "A",
    require: "^maasPrefKey",
    link: function($scope, $element) {
      $element.on("click", e => {
        let clipboardParent = e.currentTarget.previousSibling;
        let clipboardValue = clipboardParent.previousSibling.value;
        let el = document.createElement("textarea");
        el.value = clipboardValue;
        document.body.appendChild(el);
        el.select();
        document.execCommand("copy");
        document.body.removeChild(el);
      });
    }
  };
}
