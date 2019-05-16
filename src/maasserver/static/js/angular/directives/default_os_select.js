/* Copyright 2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * OS/Release select directive.
 */

function maasDefaultOsSelect() {
  return {
    restrict: "A",
    scope: {
      osInput: "@maasDefaultOsSelect",
      seriesInput: "@maasDefaultSeriesSelect"
    },
    link: function(scope, element) {
      var osElement = angular.element(element.find(scope.osInput));
      var seriesElement = angular.element(element.find(scope.seriesInput));
      if (!osElement || !seriesElement) {
        throw new Error("Unable to find os or series elements");
      }

      var selectVisableOption = function(options) {
        var first_option = null;
        angular.forEach(options, function(option) {
          option = angular.element(option);
          if (!option.hasClass("u-hide")) {
            if (first_option === null) {
              first_option = option;
            }
          }
        });
        if (first_option !== null) {
          seriesElement.val(first_option.val());
        }
      };

      var modifyOption = function(option, newOSValue, initialSkip) {
        var selected = false;
        var value = option.val();
        var split_value = value.split("/");

        // If "Default OS" is selected, then
        // only show "Default OS Release".
        if (newOSValue === "") {
          if (value === "") {
            option.removeClass("u-hide");
            option.attr("selected", "selected");
          } else {
            option.addClass("u-hide");
          }
        } else {
          if (split_value[0] === newOSValue) {
            option.removeClass("u-hide");
            if (split_value[1] === "" && !initialSkip) {
              selected = true;
              option.attr("selected", "selected");
            }
          } else {
            option.addClass("u-hide");
          }
        }
        return selected;
      };

      var switchTo = function(newOSValue, initialSkip) {
        var options = seriesElement.find("option");
        var selected = false;
        angular.forEach(options, function(option) {
          var sel = modifyOption(
            angular.element(option),
            newOSValue,
            initialSkip
          );
          if (selected === false) {
            selected = sel;
          }
        });

        // We skip selection on first load, as Django will already
        // provide the users, current selection. Without this the
        // current selection will be clobered.
        if (initialSkip) {
          return;
        }

        // See if a selection was made, if not then we need
        // to select the first visible as a default is not
        // present.
        if (!selected) {
          selectVisableOption(options);
        }
      };

      // Call switchTo any time the os changes.
      osElement.on("change", function() {
        switchTo(osElement.val(), false);
      });

      // Initialize the options.
      switchTo(osElement.val(), true);
    }
  };
}

export default maasDefaultOsSelect;
