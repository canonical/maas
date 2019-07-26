/* Copyright 2016-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS object directive.
 *
 * Directive that connects a field to an object from the websocket. The field
 * is an instant save on blur.
 */

/* @ngInject */
export function maasObjForm(JSONService) {
  /* @ngInject */
  function MAASFormController($scope) {
    "ngInject";
    this.obj = $scope.obj;
    this.manager = $scope.manager;
    this.fields = {};
    this.scope = $scope;
    this.scope.saving = false;
    this.scope.savingKeys = [];
    if (angular.isObject(this.scope.obj)) {
      this.scope.obj.$maasForm = this;
    }

    // Set the managerMethod.
    this.managerMethod = $scope.managerMethod;
    if (angular.isUndefined(this.managerMethod)) {
      this.managerMethod = "updateItem";
    }

    var self = this;
    $scope.$watch("obj", function() {
      // Update the object when it changes.
      self.obj = $scope.obj;
      if (angular.isObject(self.obj)) {
        self.obj.$maasForm = self;
      }
    });
    $scope.$on("$destroy", function() {
      // Remove the $maasForm from the object when directive is
      // deleted.
      if (angular.isObject(self.obj)) {
        delete self.obj.$maasForm;
      }
    });
  }

  // Get the current value for a field in the form.
  MAASFormController.prototype.getValue = function(key) {
    var field = this.fields[key];
    if (angular.isObject(field) && angular.isObject(field.scope)) {
      return field.scope.getValue();
    }
  };

  // Update the current value for a field in the form.
  MAASFormController.prototype.updateValue = function(key, value) {
    var field = this.fields[key];
    if (angular.isObject(field) && angular.isObject(field.scope)) {
      return field.scope.updateValue(value);
    }
  };

  // Clone the current object for this form without the $maasForm
  // property set.
  MAASFormController.prototype.cloneObject = function() {
    if (!angular.isObject(this.obj)) {
      return this.obj;
    } else {
      delete this.obj.$maasForm;
      var clonedObj = angular.copy(this.obj);
      this.obj.$maasForm = this;
      return clonedObj;
    }
  };

  // Return true if table form.
  MAASFormController.prototype.isTableForm = function() {
    if (angular.isUndefined(this.scope.tableForm)) {
      // Default is not a table form.
      return false;
    } else {
      return this.scope.tableForm;
    }
  };

  // Return true if the form should be saved on blur.
  MAASFormController.prototype.saveOnBlur = function() {
    if (angular.isUndefined(this.scope.saveOnBlur)) {
      // Default is save on blur.
      return true;
    } else {
      return this.scope.saveOnBlur;
    }
  };

  // Return true if the form is saving this field.
  MAASFormController.prototype.isSaving = function(key) {
    return this.scope.saving && this.scope.savingKeys.indexOf(key) >= 0;
  };

  // Return true if the input should show the saving spinner. This is
  // only show on inputs in forms that are using save on blur.
  MAASFormController.prototype.showInputSaving = function(key) {
    return this.saveOnBlur() && this.isSaving(key);
  };

  // Return true if any field in the form as an error.
  MAASFormController.prototype.hasErrors = function() {
    var hasErrors = false;
    angular.forEach(this.fields, function(field) {
      if (field.scope.hasErrors()) {
        hasErrors = true;
      }
    });
    if (angular.isDefined(this.errorScope)) {
      if (this.errorScope.hasErrors()) {
        hasErrors = true;
      }
    }
    return hasErrors;
  };

  // Called by maas-obj-field to register it as a editable field.
  MAASFormController.prototype.registerField = function(key, scope) {
    // Store the state of the field and its scope.
    this.fields[key] = {
      editing: false,
      scope: scope
    };

    // Watch for changes on the value of the object.
    var self = this;
    this.scope.$watch("obj." + key, function() {
      if (angular.isObject(self.obj) && !self.fields[key].editing) {
        self.fields[key].scope.updateValue(self.obj[key]);
      }
    });

    // Return the current value for the field.
    if (angular.isObject(this.obj)) {
      return this.obj[key];
    } else {
      return null;
    }
  };

  // Called by maas-obj-field to unregister it as a editable field.
  MAASFormController.prototype.unregisterField = function(key) {
    delete this.fields[key];
  };

  // Called by maas-obj-field to place field in edit mode.
  MAASFormController.prototype.startEditingField = function(key) {
    this.fields[key].editing = true;
  };

  // Called by maas-obj-field to end edit mode for the field.
  MAASFormController.prototype.stopEditingField = function(key, value) {
    var field = this.fields[key];

    // Do nothing if not save on blur.
    if (!this.saveOnBlur()) {
      field.editing = false;
      return;
    }

    // Clear errors before saving.
    field.scope.clearErrors();

    // Copy the object and update the editing field.
    var updatedObj = this.cloneObject();
    updatedObj[key] = value;
    if (updatedObj[key] === this.obj[key]) {
      // Nothing changed.
      field.editing = false;
      return;
    }

    // Update the item in the manager.
    this.scope.saving = true;
    this.scope.savingKeys = [key];
    this.updateItem(updatedObj, [key]);
  };

  // Update the item using the manager.
  MAASFormController.prototype.updateItem = function(updatedObj, keys) {
    var key = keys[0];
    var field = this.fields[key];
    var self = this;

    // Pre-process the updatedObj if one is defined.
    if (angular.isFunction(this.scope.preProcess)) {
      updatedObj = this.scope.preProcess(updatedObj, keys);
    }

    // Update the item with the manager.
    return this.manager[this.managerMethod](updatedObj).then(
      function(newObj) {
        // Update the value of the element.
        field.editing = false;
        field.scope.updateValue(newObj[key]);
        self.scope.saving = false;
        self.scope.savingKeys = [];
        if (angular.isFunction(self.scope.afterSave)) {
          self.scope.afterSave(newObj);
        }
        return newObj;
      },
      function(error) {
        var errorJson = JSONService.tryParse(error);
        if (angular.isObject(errorJson)) {
          // Add the error to each field it matches.
          angular.forEach(errorJson, function(value, key) {
            var errorField = self.fields[key];
            if (!angular.isArray(value)) {
              value = [value];
            }

            if (angular.isObject(errorField)) {
              // Error on a field we know about, place the
              // error on that field.
              errorField.scope.setErrors(value);
            } else {
              // Error on a field we don't know about, place
              // the error on the editing field. Prefixing
              // the error with the field.
              if (key !== "__all__") {
                value = value.map(function(v) {
                  return key + ": " + v;
                });
              }
              field.scope.setErrors(value);
            }
          });
        } else {
          // Add the string error to just the field error.
          field.scope.setErrors([error]);
        }
        self.scope.saving = false;
        self.scope.savingKeys = [];
        return error;
      }
    );
  };

  // Called when saveOnBlur is false to save the whole form.
  MAASFormController.prototype.saveForm = function() {
    var keys = [];
    var updatedObj = this.cloneObject();
    angular.forEach(this.fields, function(value, key) {
      value.scope.clearErrors();
      var newValue = value.scope.getValue();
      if (angular.isDefined(newValue) && updatedObj[key] !== newValue) {
        updatedObj[key] = newValue;
        keys.push(key);
      }
    });

    // Pre-process the updatedObj if one is defined.
    if (angular.isFunction(this.scope.preProcess)) {
      updatedObj = this.scope.preProcess(updatedObj, keys);
    }

    // Clear the errors on the errorScope before save.
    if (angular.isDefined(this.errorScope)) {
      this.errorScope.clearErrors();
    }

    var self = this;
    this.scope.saving = true;
    this.scope.savingKeys = keys;
    return this.manager[this.managerMethod](updatedObj).then(
      function(newObj) {
        self.scope.saving = false;
        self.scope.savingKeys = [];
        if (angular.isFunction(self.scope.afterSave)) {
          self.scope.afterSave(newObj);
        }
        return newObj;
      },
      function(error) {
        var errorJson = JSONService.tryParse(error);
        if (angular.isObject(errorJson)) {
          // Add the error to each field it matches.
          angular.forEach(errorJson, function(value, key) {
            var errorField = self.fields[key];
            if (!angular.isArray(value)) {
              value = [value];
            }

            if (angular.isObject(errorField)) {
              // Error on a field we know about, place the
              // error on that field.
              errorField.scope.setErrors(value);
            } else {
              if (key !== "__all__") {
                value = value.map(function(v) {
                  return key + ": " + v;
                });
              }
              // Error on a field we don't know about, place
              // the error on errorScope if set.
              if (angular.isDefined(self.errorScope)) {
                self.errorScope.setErrors(value);
              } else {
                // No error scope, just log to console.
                console.log(value); // eslint-disable-line no-console
              }
            }
          });
        } else {
          // Add the string error to just the field error.
          if (angular.isDefined(self.errorScope)) {
            self.errorScope.setErrors([error]);
          } else {
            // No error scope, just log to console.
            console.log(error); // eslint-disable-line no-console
          }
        }
        self.scope.saving = false;
        self.scope.savingKeys = [];
        return error;
      }
    );
  };

  return {
    restrict: "E",
    scope: {
      obj: "=",
      manager: "=",
      managerMethod: "@",
      preProcess: "=",
      afterSave: "=",
      tableForm: "=",
      saveOnBlur: "=",
      inline: "=",
      ngDisabled: "&"
    },
    transclude: true,
    template:
      '<form class="p-form" data-ng-class="{saving: saving, ' +
      "'p-form--inline': inline, " +
      "'p-form--stacked': tableForm}\" " +
      "ng-transclude></form>",
    controller: MAASFormController
  };
}

export function maasObjFieldGroup() {
  function MAASGroupController($scope, $timeout) {
    "ngInject";
    this.fields = {};
    this.scope = $scope;
    this.scope.saving = false;
    this.scope.savingKeys = [];
    this.timeout = $timeout;

    var self = this;
    this.scope.isEditing = function() {
      var editing = false;
      angular.forEach(self.fields, function(value) {
        if (!editing) {
          editing = value.editing;
        }
      });
      return editing;
    };
  }

  // Return true if table form.
  MAASGroupController.prototype.isTableForm = function() {
    return this.formController.isTableForm();
  };

  // Return true if should save on blur.
  MAASGroupController.prototype.saveOnBlur = function() {
    return this.formController.saveOnBlur();
  };

  // Return true if group is saving.
  MAASGroupController.prototype.isSaving = function(key) {
    return this.scope.saving && this.scope.savingKeys.indexOf(key) >= 0;
  };

  // Return true if the input should show the saving spinner. This is
  // only show on inputs in forms that are using save on blur.
  MAASGroupController.prototype.showInputSaving = function(key) {
    // In a group we say the entire group is saving, not just that
    // one key in the field is being saved.
    return this.saveOnBlur() && this.scope.saving;
  };

  // Called by maas-obj-field to register it as a editable field.
  MAASGroupController.prototype.registerField = function(key, scope) {
    // Store the state of the field and its scope.
    this.fields[key] = {
      editing: false,
      scope: scope
    };
    return this.formController.registerField(key, scope);
  };

  // Called by maas-obj-field to unregister it as a editable field.
  MAASGroupController.prototype.unregisterField = function(key) {
    delete this.fields[key];
    this.formController.unregisterField(key);
  };

  // Called by maas-obj-field to place field in edit mode.
  MAASGroupController.prototype.startEditingField = function(key) {
    this.fields[key].editing = true;

    // Set all fields in the group as editing in the formController.
    var self = this;
    angular.forEach(this.fields, function(value, key) {
      self.formController.startEditingField(key);
    });
  };

  // Called by maas-obj-field to exit edit mode for the field.
  MAASGroupController.prototype.stopEditingField = function(key, value) {
    var field = this.fields[key];
    field.editing = false;

    // Exit early if not save on blur.
    if (!this.saveOnBlur()) {
      return;
    }

    // Delay the handling of stop to make sure start is not called on
    // the next field in the group.
    var self = this;
    this.timeout(function() {
      // If any other fields are in edit mode then nothing to do.
      var editing = false;
      angular.forEach(self.fields, function(value) {
        if (!editing) {
          editing = value.editing;
        }
      });
      if (editing) {
        return;
      }

      // Copy the object and update the editing fields.
      var keys = [];
      var changed = false;
      var updatedObj = self.formController.cloneObject();
      angular.forEach(self.fields, function(value, key) {
        value.scope.clearErrors();
        var newValue = value.scope.getValue();
        if (angular.isDefined(newValue) && updatedObj[key] !== newValue) {
          keys.push(key);
          updatedObj[key] = newValue;
          changed = true;
        }
      });
      if (!changed) {
        return;
      }

      // Place the field that actually triggered the update first.
      var keyIdx = keys.indexOf(key);
      if (keyIdx !== -1) {
        keys.splice(keyIdx, 1);
        keys.splice(0, 0, key);
      }

      // Save the object.
      self.scope.saving = true;
      self.scope.savingKeys = keys;
      self.formController.updateItem(updatedObj, keys).then(
        function(obj) {
          self.scope.saving = false;
          self.scope.savingKeys = [];
          return obj;
        },
        function(error) {
          self.scope.saving = false;
          self.scope.savingKeys = [];
          return error;
        }
      );
    }, 10); // Really short has to be next click.
  };

  return {
    restrict: "E",
    require: ["^^maasObjForm", "maasObjFieldGroup"],
    scope: {},
    transclude: true,
    template:
      '<div class="form__siblings" ' +
      "data-ng-class=\"{'is-active': isEditing()}\" " +
      "data-ng-transclude></div>",
    controller: MAASGroupController,
    link: {
      pre: function(scope, element, attrs, controllers) {
        // Set formController on the MAASGroupController to
        // point to its parent MAASFormController. This is done in
        // pre-link so the controller has the formController before
        // registerField is called.
        controllers[1].formController = controllers[0];

        // Set ngDisabled on this scope from the form controller.
        scope.ngDisabled = controllers[0].scope.ngDisabled;

        // Set the object to always be the same on the scope.
        controllers[0].scope.$watch("obj", function(obj) {
          scope.obj = obj;
        });
      }
    }
  };
}

/* @ngInject */
export function maasObjField($compile) {
  return {
    restrict: "E",
    require: ["^^maasObjForm", "?^^maasObjFieldGroup"],
    scope: {
      onChange: "=",
      subtleText: "@"
    },
    transclude: true,
    template: "<div data-ng-transclude></div>",
    link: function(scope, element, attrs, controllers) {
      // Select the controller based on which is available.
      var controller = controllers[1];
      if (!angular.isObject(controller)) {
        controller = controllers[0];
      }

      // Set ngDisabled from the parent controller.
      scope.ngDisabled = controller.scope.ngDisabled;

      element.addClass("p-form__group");

      if (!attrs.disableRow) {
        element.addClass("row");
      }

      if (attrs.subtle !== "false") {
        element.addClass("form__group--subtle");
      }

      // type and key required.
      var missingAttrs = [];
      if (!angular.isString(attrs.type) || attrs.type.length === 0) {
        missingAttrs.push("type");
      }
      if (!angular.isString(attrs.key) || attrs.key.length === 0) {
        missingAttrs.push("key");
      }
      if (missingAttrs.length > 0) {
        throw new Error(
          missingAttrs.join(", ") + " are required on maas-obj-field."
        );
      }
      if (angular.isString(attrs.disabled)) {
        scope.ngDisabled = function() {
          return true;
        };
      }

      // Remove transcluded element.
      element.find("div").remove();

      // Render the label.
      var label = attrs.label || attrs.key;

      if (attrs.disableLabel !== "true" && !(attrs.type === "hidden")) {
        var labelElement = angular.element("<label/>");
        labelElement.attr("for", attrs.key);
        labelElement.text(label);
        labelElement.addClass("p-form__label");
        if (attrs.labelWidth) {
          labelElement.addClass("col-" + attrs.labelWidth);

          if (attrs.labelWidthMobile) {
            labelElement.addClass("col-small-" + attrs.labelWidthMobile);
          }
          if (attrs.labelWidthTablet) {
            labelElement.addClass("col-medium-" + attrs.labelWidthTablet);
          }
        }
        if (attrs.labelLeft === "true") {
          labelElement.addClass("u-padding--left");
          labelElement.addClass("u-position--relative");
        }
        element.append(labelElement);

        // Add a label info icon with tooltip.
        if (angular.isString(attrs.labelInfo) && attrs.labelInfo.length > 0) {
          var infoWrapper = angular.element("<span>&nbsp;</span>");
          infoWrapper.addClass("p-tooltip--btm-right");

          var infoIcon = angular.element("<i/>");
          if (attrs.labelInfoIcon) {
            infoIcon.addClass("p-icon--" + attrs.labelInfoIcon);
          } else {
            infoIcon.addClass("p-icon--information");
          }
          infoIcon.attr("aria-describedby", attrs.key + "-tooptip");

          var infoTooltip = angular.element("<p></p>");
          infoTooltip.addClass("p-tooltip__message");
          infoTooltip.text(attrs.labelInfo);
          infoTooltip.attr("id", attrs.key + "-tooptip");

          infoWrapper.append(infoIcon);
          infoWrapper.append(infoTooltip);

          labelElement.append(infoWrapper);

          // prevents the icon from being clickable
          infoIcon.bind("click", function(evt) {
            evt.preventDefault();
          });
        }
      }

      // Add the wrapper for the input.
      var inputWrapper = angular.element("<div></div>");
      inputWrapper.addClass("p-form__control");

      if (attrs.inputWidthMobile) {
        inputWrapper.addClass("col-small-" + attrs.inputWidthMobile);
      }
      if (attrs.inputWidthTablet) {
        inputWrapper.addClass("col-medium-" + attrs.inputWidthTablet);
      }
      if (attrs.inputWidth) {
        inputWrapper.addClass("col-" + attrs.inputWidth);
      }

      // Render the input based on the type.
      var placeholder = attrs.placeholder || label;
      var inputElement = null;
      if (
        attrs.type === "text" ||
        attrs.type === "textarea" ||
        attrs.type === "password"
      ) {
        if (attrs.type === "text") {
          inputElement = $compile(
            '<input type="text" id="' +
              attrs.key +
              '" placeholder="' +
              placeholder +
              '"' +
              'data-ng-disabled="ngDisabled()">'
          )(scope);
        } else if (attrs.type === "textarea") {
          inputElement = $compile(
            '<textarea id="' +
              attrs.key +
              '" placeholder="' +
              placeholder +
              '"' +
              'data-ng-disabled="ngDisabled()">' +
              "</textarea>"
          )(scope);
        } else if (attrs.type === "password") {
          inputElement = $compile(
            '<input type="password" id="' +
              attrs.key +
              '" placeholder="' +
              placeholder +
              '"' +
              'data-ng-disabled="ngDisabled()">'
          )(scope);
        }

        // Allow enter on blur, by default.
        if (attrs.blurOnEnter) {
          inputElement.bind("keydown keypress", function(evt) {
            if (evt.which === 13) {
              inputElement.blur();
              evt.preventDefault();
            }
          });
        }

        // Revert value on esc.
        inputElement.bind("keydown keypress", function(evt) {
          if (evt.which === 27) {
            inputElement.val(controller.scope.obj[attrs.key]);
            inputElement.blur();
            evt.preventDefault();
          }
        });

        // Set input value if 'value' attr provided
        if (attrs.value) {
          scope.$applyAsync(function() {
            inputElement.val(attrs.value);
          });
        }

        // Register the field with the controller and set the
        // current value for the field.
        var currentValue = controller.registerField(attrs.key, scope);
        inputElement.val(currentValue);

        // When element is in focus then editing is on.
        inputElement.on("focus", function() {
          scope.$apply(function() {
            controller.startEditingField(attrs.key);
          });
        });

        // When element is not in focus then editing is done.
        inputElement.on("blur", function() {
          scope.$apply(function() {
            controller.stopEditingField(attrs.key, inputElement.val());
          });
        });

        // Called by controller to update the value.
        scope.updateValue = function(newValue) {
          inputElement.val(newValue);
        };

        // Called by controller to get the value.
        scope.getValue = function() {
          return inputElement.val();
        };
      } else if (attrs.type === "options") {
        // Requires the options attribute on the element. This
        // is copied directly into the ngOptions directive on
        // the select.
        var options = attrs.options;
        if (!angular.isString(options) || options.length === 0) {
          throw new Error(
            "options attribute is required on type " +
              "'options' on maas-obj-field."
          );
        }

        // Placeholder by default is disabled, allow it to be
        // enabled.
        var disabled = "disabled";
        if (attrs.placeholderEnabled === "true") {
          disabled = "";
        }

        // Create a child scope of the parent scope for this
        // directive. Since this directive is created with an
        // isolated scope we need the child to use the parent so
        // ngOptions can use properties defined in that scope.
        var childScope = scope.$parent.$new();
        childScope._ngDisabled = scope.ngDisabled;
        childScope._selectValue = controller.registerField(attrs.key, scope);
        childScope._selectNgChange = function() {
          scope._change();
          controller.stopEditingField(attrs.key, childScope._selectValue);
        };

        // Construct the select.
        inputElement = $compile(
          '<select id="' +
            attrs.key +
            '" ' +
            'data-ng-model="_selectValue" ' +
            'data-ng-options="' +
            options +
            '"' +
            'data-ng-change="_selectNgChange()"' +
            'data-ng-disabled="_ngDisabled()">' +
            '<option value="" ' +
            disabled +
            ">" +
            placeholder +
            "</option></select>"
        )(childScope);

        // Called by controller to update the value.
        scope.updateValue = function(newValue) {
          childScope._selectValue = newValue;
        };

        // Called by controller to get the value.
        scope.getValue = function() {
          return childScope._selectValue;
        };
      } else if (attrs.type === "checkboxes") {
        // Requires the values attribute on the element.
        var values = attrs.values;
        if (!angular.isString(values) || values.length === 0) {
          throw new Error(
            "values attribute is required on type " +
              "'checkboxes' on maas-obj-field."
          );
        }

        // Create a child scope of the parent scope for this
        // directive. Since this directive is created with an
        // isolated scope we need the child to use the parent so
        // values can come from the parent scope.
        var checkScope = scope.$parent.$new();
        checkScope._selectedValues = controller.registerField(attrs.key, scope);
        checkScope._checked = function(val) {
          return checkScope._selectedValues.indexOf(val) > -1;
        };
        checkScope._toggleChecked = function(val) {
          var idx = checkScope._selectedValues.indexOf(val);
          if (idx > -1) {
            // Uncheck.
            checkScope._selectedValues.splice(idx, 1);
          } else {
            // Check.
            checkScope._selectedValues.push(val);
          }
        };

        // Construct the checkbox list.
        inputElement = angular.element(
          [
            '<div class="p-form__group" ',
            'style="padding-top: .2rem;" ',
            'data-ng-repeat="val in ' + values + '">',
            '<input id="' + attrs.key + "_" + "{$ val $}",
            '" type="checkbox" value="{$ val $}" ',
            'class="checkbox" ',
            'data-ng-checked="_checked(val)" ',
            'data-ng-click="_toggleChecked(val)">',
            '<label for="' + attrs.key + "_",
            "{$ val $}" + '" ',
            'class="checkbox-label">{$ val $}</label>',
            "</div>"
          ].join("")
        );
        inputElement = $compile(inputElement)(checkScope);

        // Called by controller to update the value.
        scope.updateValue = function(newValue) {
          checkScope._selectedValues = newValue;
        };

        // Called by controller to get the value.
        scope.getValue = function() {
          return checkScope._selectedValues;
        };
      } else if (attrs.type === "tags") {
        var tagsScope = scope.$new();
        var tags = controller.registerField(attrs.key, scope);
        tagsScope._tags = tags.map(function(val) {
          return { text: val };
        });

        // Construct the tags input.
        inputElement = angular.element(
          [
            '<span data-ng-if="ngDisabled()" ',
            'data-ng-repeat="tag in _tags">',
            "{$ tag.text $} </span>",
            '<tags-input id="' + attrs.key + '" ',
            'data-ng-model="_tags" ',
            'data-ng-if="!ngDisabled()" ',
            'placeholder="' + placeholder + '" ',
            'data-ng-change="_change()" ',
            'allow-tags-pattern="[\\w-]+"></tags-input>'
          ].join("")
        );
        inputElement = $compile(inputElement)(tagsScope);

        // Called by controller to update the value.
        scope.updateValue = function(newValue) {
          tagsScope._tags = newValue.map(function(val) {
            return { text: val };
          });
        };

        // Called by controller to get the value.
        scope.getValue = function() {
          return tagsScope._tags.map(function(val) {
            return val.text;
          });
        };
      } else if (attrs.type === "hidden") {
        var hiddenScope = scope.$new();
        hiddenScope._toggle = controller.registerField(attrs.key, scope);
        inputElement = angular.element(
          [
            '<input type="hidden" name="' + attrs.key + '" ',
            'id="' + attrs.key + '" ',
            'value="' + attrs.value + '">',
            "</input>"
          ].join("")
        );
        inputElement = $compile(inputElement)(hiddenScope);
        scope.getValue = function() {
          return attrs.value;
        };
        scope.updateValue = function() {
          return null;
        };
      } else if (attrs.type === "onoffswitch") {
        var switchScope = scope.$new();
        switchScope._toggle = controller.registerField(attrs.key, scope);
        switchScope._changed = function() {
          scope._change();
          controller.startEditingField(attrs.key);
          controller.stopEditingField(attrs.key, switchScope.getValue());
        };

        // Construct the on and off switch toggle.
        inputElement = angular.element(
          [
            '<div class="maas-p-switch">',
            '<input type="checkbox" name="' + attrs.key + '" ',
            'class="maas-p-switch--input" ',
            'id="' + attrs.key + '" ',
            'data-ng-model="_toggle" ',
            'data-ng-change="_changed()">',
            '<div class="maas-p-switch--mask"></div>',
            "</div>"
          ].join("")
        );
        inputElement = $compile(inputElement)(switchScope);

        // Called by controller to update the value.
        scope.updateValue = function(newValue) {
          // WARNING: This code is difficult to unit test, since
          // we could not figure out how to get the
          // isolateScope() from the transcluded element. Be sure
          // to manually test versions of this toggle with and
          // without the on-value and off-value attributes, such
          // as by verifying that both the on/off toggle on both
          // the discovery page and the subnet details page work.
          if (attrs.onValue && attrs.onValue === newValue) {
            switchScope._toggle = true;
          } else if (attrs.offValue && attrs.offValue === newValue) {
            switchScope._toggle = false;
          } else {
            switchScope._toggle = newValue;
          }
        };

        // Called by controller to get the value.
        scope.getValue = function() {
          // WARNING: This code is difficult to unit test, since
          // we could not figure out how to get the
          // isolateScope() from the transcluded element. Be sure
          // to manually test versions of this toggle with and
          // without the on-value and off-value attributes, such
          // as by verifying that both the on/off toggle on both
          // the discovery page and the subnet details page work.
          if (switchScope._toggle) {
            if (attrs.onValue) {
              return attrs.onValue;
            } else {
              return true;
            }
          } else {
            if (attrs.offValue) {
              return attrs.offValue;
            } else {
              return false;
            }
          }
        };
      } else if (attrs.type == "slider") {
        var sliderScope = scope.$new();
        sliderScope._slider = controller.registerField(attrs.key, scope);
        sliderScope._ngDisabled = scope.ngDisabled;

        // Construct the tags input.
        inputElement = angular.element(
          [
            '<div class="p-slider__wrapper">',
            '<input class="p-slider" type="range"',
            'min="' + attrs.min + '" max="' + attrs.max + '" ',
            'value="1" step="' + attrs.step + '" ',
            'id="' + attrs.key + '" ',
            'data-ng-model="_slider" data-ng-disabled="',
            '_ngDisabled()">',
            '<input class="p-slider__input" type="text" ',
            'maxlength="3" id="' + attrs.key + '-input" ',
            'data-ng-model="_slider" disabled="disabled" ',
            "></div>"
          ].join("")
        );
        inputElement = $compile(inputElement)(sliderScope);

        // Called by controller to update the value.
        scope.updateValue = function(newValue) {
          sliderScope._slider = newValue;
        };

        // Called by controller to get the value.
        scope.getValue = function() {
          return sliderScope._slider;
        };
      } else {
        throw new Error("Unknown type on maas-obj-field: " + attrs.type);
      }

      // Called on change.
      scope._change = function() {
        if (angular.isFunction(scope.onChange)) {
          scope.onChange(attrs.key, controller.getValue(attrs.key), controller);
        }
      };

      // Copy input class to the input element.
      if (attrs.inputClass) {
        inputElement.addClass(attrs.inputClass);
      }
      inputWrapper.append(inputElement);

      // Errors element.
      var errorsElement = angular.element(
        '<ul class="p-list u-no-margin--bottom"></ul>'
      );
      if (!controller.isTableForm()) {
        errorsElement.addClass("form__error");
      }
      inputWrapper.append(errorsElement);

      // Help text elements
      if (attrs.helpText) {
        var helpTextElement = angular.element("<p>" + attrs.helpText + "</p>");
        helpTextElement.addClass("p-form-help-text");
        inputWrapper.append(helpTextElement);
      }

      // Called by controller to clear all errors.
      scope.clearErrors = function() {
        inputElement.removeClass("ng-dirty");
        inputElement.removeClass("p-form-validation__input");
        inputWrapper.removeClass("p-form-validation");
        inputWrapper.removeClass("is-error");
        inputWrapper.removeClass("u-no-margin--top");
        errorsElement.empty();
      };

      // Called by controller to set errors.
      scope.setErrors = function(errors) {
        if (errors.length > 0) {
          inputWrapper.addClass("p-form-validation");
          inputWrapper.addClass("is-error");
          inputWrapper.addClass("u-no-margin--top");
          inputElement.addClass("ng-dirty");
          inputElement.addClass("p-form-validation__input");
          angular.forEach(errors, function(error) {
            errorsElement.append(
              '<li class="p-form-validation__message">' +
                "<strong>Error:</strong> " +
                error +
                "</li>"
            );
          });
        }
      };

      // Called by controller to see if error is set on field.
      scope.hasErrors = function() {
        return inputWrapper.hasClass("is-error");
      };

      // Subtle text element.
      if (attrs.subtleText) {
        var subtleTextElement = $compile(
          angular.element(
            '<p class="p-form-help-text" ' + 'data-ng-bind="subtleText"></p>'
          )
        )(scope);
        inputWrapper.append(subtleTextElement);
      }
      element.append(inputWrapper);

      // Watch the showing of saving spinner. Update the elements
      // correctly to show the saving.
      scope.$watch(
        function() {
          return controller.showInputSaving(attrs.key);
        },
        function(value) {
          if (value) {
            inputWrapper.children(":first").addClass("u-border--information");
            labelElement.prepend(
              '<i class="obj-saving icon ' +
                'p-icon--spinner u-animation--spin"></i>'
            );
            inputWrapper.addClass("p-tooltip");
            inputWrapper.addClass("p-tooltip--bottom");
            inputWrapper.addClass("u-no-margin--top");
            inputWrapper.attr("aria-label", "Saving");
          } else {
            inputWrapper
              .children(":first")
              .removeClass("u-border--information");
            if (labelElement) {
              labelElement.find("i.obj-saving").remove();
            }
            inputWrapper.removeClass("p-tooltip");
            inputWrapper.removeClass("p-tooltip--right");
            inputWrapper.addClass("u-no-margin--top");
            inputWrapper.removeAttr("aria-label");
          }
        }
      );

      // Called when the scope is destroyed.
      scope.$on("$destroy", function() {
        controller.unregisterField(attrs.key);
      });
    }
  };
}

export function maasObjSave() {
  return {
    restrict: "A",
    require: ["^^maasObjForm"],
    scope: {},
    link: function(scope, element, attrs, controllers) {
      // Only allow maas-obj-save when saveOnBlur is false.
      var controller = controllers[0];
      if (controller.saveOnBlur()) {
        throw new Error(
          "maas-obj-save is only allowed when save-on-blur is " +
            "set to false."
        );
      }

      element.on("click", function() {
        scope.$apply(function() {
          controller.saveForm();
        });
      });
    }
  };
}

/* @ngInject */
export function maasObjErrors($compile) {
  return {
    restrict: "E",
    require: ["^^maasObjForm"],
    scope: {},
    template: '<ul class="p-list u-no-margin--top"></ul>',
    link: function(scope, element, attrs, controllers) {
      // Set on the controller the global error handler.
      controllers[0].errorScope = scope;
      var ul = element.find("ul");

      // Called by controller to clear all errors.
      scope.clearErrors = function() {
        ul.empty();
      };

      // Called by controller to set errors.
      scope.setErrors = function(errors) {
        if (errors.length > 0) {
          scope.errors = errors;
          for (var i = 0; i < scope.errors.length; i++) {
            ul.append(
              $compile(
                '<li class="p-list__item">' +
                  '<i class="p-icon--error"></i> ' +
                  '<span ng-bind="errors[' +
                  i +
                  ']"></span>' +
                  "</li>"
              )(scope)
            );
          }
        }
      };

      // Called by controller to see if error is set on field.
      scope.hasErrors = function() {
        return ul.children().length > 0;
      };
    }
  };
}

export function maasObjSaving() {
  return {
    restrict: "E",
    require: "^^maasObjForm",
    scope: {},
    transclude: true,
    template: [
      '<span data-ng-if="saving">',
      '<i class="p-icon--loading u-animation--spin"></i>',
      "<span data-ng-transclude></span>",
      "</span>"
    ].join(""),
    link: function(scope, element, attrs, controller) {
      scope.saving = false;
      scope.$watch(
        function() {
          return controller.scope.saving;
        },
        function(value) {
          scope.saving = value;
        }
      );
    }
  };
}

export function maasObjShowSaving() {
  return {
    restrict: "A",
    require: "^^maasObjForm",
    link: function(scope, element, attrs, controller) {
      scope.$watch(
        function() {
          return controller.scope.saving;
        },
        function(value) {
          if (value) {
            element.removeClass("ng-hide");
          } else {
            element.addClass("ng-hide");
          }
        }
      );
    }
  };
}

export function maasObjHideSaving() {
  return {
    restrict: "A",
    require: "^^maasObjForm",
    link: function(scope, element, attrs, controller) {
      scope.$watch(
        function() {
          return controller.scope.saving;
        },
        function(value) {
          if (value) {
            element.addClass("ng-hide");
          } else {
            element.removeClass("ng-hide");
          }
        }
      );
    }
  };
}
