/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for MAAS object form.
 */

import { makeName } from "testing/utils";

describe("maasObjForm", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Get required angular pieces and create a new scope before each test.
  var $scope, $timeout, $compile, $q;
  beforeEach(inject(function($rootScope, $injector) {
    $scope = $rootScope.$new();
    $timeout = $injector.get("$timeout");
    $compile = $injector.get("$compile");
    $q = $injector.get("$q");
  }));

  // Return the compiled directive.
  function compileDirective(html) {
    html = "<div>" + html + "</div>";
    var directive = $compile(html)($scope);
    $scope.$digest();
    return directive.children(":first");
  }

  // Changes value on field.
  function changeFieldValue(field, val) {
    // Grab focus.
    field.triggerHandler("focus");
    $scope.$digest();

    // Set the new value.
    field.val(val);
    $scope.$digest();

    // Lose focus.
    field.triggerHandler("blur");
    $scope.$digest();
  }

  // Return the list of rendered errors in the element.
  function getErrorList(element) {
    var errors = [];
    var lis = element.find("ul.p-list").children();
    lis.each(function() {
      errors.push(angular.element(this).text());
    });
    return errors;
  }

  describe("inline form", function() {
    it("adds 'p-form--inline'", function() {
      $scope.obj = {};
      $scope.manager = {};
      var html = [
        '<maas-obj-form obj="obj" manager="manager" inline="true">',
        "</maas-obj-form>"
      ].join("");
      var directive = compileDirective(html);
      var form = directive.find("form");
      expect(form.hasClass("p-form--inline")).toBe(true);
    });
  });

  describe("input type=text", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {
        updateItem: jasmine.createSpy().and.returnValue($q.defer().promise)
      };
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="text" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("creates input with type 'text'", function() {
      var inputField = angular.element(directive.find("#key"));
      expect(inputField.prop("nodeName")).toBe("INPUT");
      expect(inputField.attr("type")).toBe("text");
    });

    it("sets placeholder", function() {
      var inputField = angular.element(directive.find("#key"));
      expect(inputField.attr("placeholder")).toBe("Placeholder");
    });

    it("adds label with width", function() {
      var labelField = angular.element(directive.find("label"));
      expect(labelField.text()).toBe("Key");
      expect(labelField.hasClass("col-2")).toBe(true);
    });

    it("adds inputWrapper with width", function() {
      var labelField = angular.element(directive.find("label "));
      var inputWrapper = angular.element(labelField.next("div"));
      expect(inputWrapper.hasClass("col-3")).toBe(true);
    });

    it("reverts value on esc", function() {
      var inputField = angular.element(directive.find("#key"));
      inputField.triggerHandler("focus");
      inputField.val(makeName("newValue"));

      // Send esc.
      var evt = angular.element.Event("keydown");
      evt.which = 27;
      inputField.trigger(evt);

      expect(inputField.val()).toBe("");
    });

    it("sets $maasForm on obj", function() {
      expect($scope.obj.$maasForm).toBeDefined();
    });

    it("hasErrors returns true if is-error class exists", function() {
      var control = angular.element(directive.find(".p-form__control"));
      control.addClass("is-error");
      expect($scope.obj.$maasForm.hasErrors()).toBe(true);
    });
  });

  describe("textarea", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {};
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="textarea" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("creates textarea", function() {
      var textarea = angular.element(directive.find("#key"));
      expect(textarea.prop("nodeName")).toBe("TEXTAREA");
    });

    it("sets placeholder", function() {
      var textarea = angular.element(directive.find("#key"));
      expect(textarea.attr("placeholder")).toBe("Placeholder");
    });

    it("adds label with width", function() {
      var labelField = angular.element(directive.find("label"));
      expect(labelField.text()).toBe("Key");
      expect(labelField.hasClass("col-2")).toBe(true);
    });

    it("adds inputWrapper with width", function() {
      var labelField = angular.element(directive.find("label "));
      var inputWrapper = angular.element(labelField.next("div"));
      expect(inputWrapper.hasClass("col-3")).toBe(true);
    });
  });

  describe("input type=password", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {
        updateItem: jasmine.createSpy().and.returnValue($q.defer().promise)
      };
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="password" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("creates input with type 'password'", function() {
      var inputField = angular.element(directive.find("#key"));
      expect(inputField.prop("nodeName")).toBe("INPUT");
      expect(inputField.attr("type")).toBe("password");
    });

    it("sets placeholder", function() {
      var inputField = angular.element(directive.find("#key"));
      expect(inputField.attr("placeholder")).toBe("Placeholder");
    });

    it("adds label with width", function() {
      var labelField = angular.element(directive.find("label"));
      expect(labelField.text()).toBe("Key");
      expect(labelField.hasClass("col-2")).toBe(true);
    });

    it("adds inputWrapper with width", function() {
      var labelField = angular.element(directive.find("label "));
      var inputWrapper = angular.element(labelField.next("div"));
      expect(inputWrapper.hasClass("col-3")).toBe(true);
    });

    it("reverts value on esc", function() {
      var inputField = angular.element(directive.find("#key"));
      inputField.triggerHandler("focus");
      inputField.val(makeName("newValue"));

      // Send esc.
      var evt = angular.element.Event("keydown");
      evt.which = 27;
      inputField.trigger(evt);

      expect(inputField.val()).toBe("");
    });

    it("sets $maasForm on obj", function() {
      expect($scope.obj.$maasForm).toBeDefined();
    });

    it("hasErrors returns true if has-error class exists", function() {
      var control = angular.element(directive.find(".p-form__control"));
      control.addClass("is-error");
      expect($scope.obj.$maasForm.hasErrors()).toBe(true);
    });
  });

  describe("select", function() {
    var directive, options;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {};
      $scope.options = [
        {
          id: 0,
          text: "test"
        }
      ];
      options = "option.id as option.text for option in options";
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="options" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3" options="' + options + '">',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("creates select", function() {
      var select = angular.element(directive.find("#key"));
      expect(select.prop("nodeName")).toBe("SELECT");
      expect(select.attr("data-ng-options")).toBe(options);
    });

    it("adds placeholder option", function() {
      var select = angular.element(directive.find("#key"));
      var placeholder = angular.element(select.find('option[value=""]'));
      expect(placeholder.attr("disabled")).toBe("disabled");
      expect(placeholder.text()).toBe("Placeholder");
    });

    it("creates placeholder enabled", function() {
      options = "option.id as option.text for option in options";
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="options" key="key" ',
        'placeholder-enabled="true" options="' + options + '">',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
      var select = angular.element(directive.find("#key"));
      var placeholder = angular.element(select.find('option[value=""]'));
      expect(placeholder.attr("disabled")).toBeUndefined();
    });

    it("adds label with width", function() {
      var labelField = angular.element(directive.find("label"));
      expect(labelField.text()).toBe("Key");
      expect(labelField.hasClass("col-2")).toBe(true);
    });

    it("adds inputWrapper with width", function() {
      var labelField = angular.element(directive.find("label "));
      var inputWrapper = angular.element(labelField.next("div"));
      expect(inputWrapper.hasClass("col-3")).toBe(true);
    });

    it("calls on-change function", function() {
      var options;
      $scope.obj = {};
      $scope.manager = {};
      $scope.changeForm = function(key, val, form) {
        form.updateValue("key2", "new value");
      };
      $scope.options = [
        {
          id: 0,
          text: "0"
        },
        {
          id: 1,
          text: "1"
        }
      ];
      options = "option.id as option.text for option in options";
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="options" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'on-change="changeForm" ',
        'input-width="3" options="' + options + '">',
        "</maas-obj-field>",
        '<maas-obj-field type="text" key="key2" label="Key2" ',
        'placeholder="" label-width="2" ',
        'input-width="3"',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);

      //var input = directive.find(
      //    'maas-obj-field[key="key"]').find('input');
      $scope.obj.key = [0];
      $scope.$digest();
      // XXX lamont 2017-03-08  Blake to fix.
      //expect($scope.obj.key2).toBe("new value");
    });
  });

  describe("checkboxes", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {
        key: []
      };
      $scope.manager = {};
      $scope.values = ["one", "two", "three"];
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="checkboxes" key="key" label="Key" ',
        'label-width="2" input-width="3" ',
        'values="values">',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("creates muliple divs with checkboxes", function() {
      var divs = angular.element(directive.find("div.p-form__group"));
      expect(divs.length).toBe(3);
      angular.forEach($scope.values, function(value, idx) {
        var div = angular.element(divs[idx]);
        var input = angular.element(div.find("input"));
        var label = angular.element(div.find("label"));
        expect(input.attr("id")).toBe("key_" + value);
        expect(label.attr("for")).toBe("key_" + value);
        expect(label.text()).toBe(value);
      });
    });

    it("adds label with width", function() {
      var labelField = angular.element(directive.find('label[for="key"]'));
      expect(labelField.text()).toBe("Key");
      expect(labelField.hasClass("col-2")).toBe(true);
    });
  });

  describe("tags", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {
        key: []
      };
      $scope.manager = {};
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="tags" key="key" label="Key" ',
        'label-width="2" input-width="3">',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("creates tags-input", function() {
      var tags = directive.find("tags-input");
      expect(tags.length).toBe(1);
    });

    it("adds label with width", function() {
      var labelField = angular.element(directive.find('label[for="key"]'));
      expect(labelField.text()).toBe("Key");
      expect(labelField.hasClass("col-2")).toBe(true);
    });
  });

  describe("onoffswitch", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {
        key: false
      };
      $scope.manager = {};
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="onoffswitch" key="key" label="Key" ',
        'label-width="2" input-width="3">',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("creates onoffswitch", function() {
      var onoff = angular.element(directive.find("div.maas-p-switch"));
      expect(onoff.length).toBe(1);
    });

    it("adds label with width", function() {
      var labelField = angular.element(directive.find('label[for="key"]'));
      expect(labelField.text()).toBe("Key");
      expect(labelField.hasClass("col-2")).toBe(true);
    });
  });

  describe("slider", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {
        key: []
      };
      $scope.manager = {};
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="slider" key="key" label="Key" ',
        'label-width="2" input-width="3">',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("creates input", function() {
      var slider = directive.find("input");
      expect(slider.length).toBe(2);
    });

    it("adds label with width", function() {
      var labelField = angular.element(directive.find('label[for="key"]'));
      expect(labelField.text()).toBe("Key");
      expect(labelField.hasClass("col-2")).toBe(true);
    });
  });

  describe("hidden", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {
        key: false
      };
      $scope.manager = {};
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="hidden" key="key" label="Key" ',
        'value="value">',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("creates hidden input field", function() {
      var onoff = angular.element(directive.find("input"));
      expect(onoff.length).toBe(1);
    });
  });

  describe("single field", function() {
    var directive, updateItemMethod, saveDefer;
    beforeEach(function() {
      $scope.obj = {
        key: makeName("key")
      };
      saveDefer = $q.defer();
      updateItemMethod = jasmine.createSpy();
      updateItemMethod.and.returnValue(saveDefer.promise);
      $scope.manager = {
        updateItem: updateItemMethod
      };
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="text" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("sets input to value", function() {
      var field = angular.element(directive.find("#key"));
      expect(field.val()).toBe($scope.obj.key);
    });

    it("updates input to value when not in focus", function() {
      var field = angular.element(directive.find("#key"));
      expect(field.val()).toBe($scope.obj.key);
      $scope.obj.key = makeName("new_key");
      $scope.$digest();
      expect(field.val()).toBe($scope.obj.key);
    });

    it("doesn't update input to value when in focus", function() {
      var field = angular.element(directive.find("#key"));
      expect(field.val()).toBe($scope.obj.key);
      field.triggerHandler("focus");
      $scope.obj.key = makeName("new_key");
      $scope.$digest();
      expect(field.val()).not.toBe($scope.obj.key);
    });

    it("sets 'saving' class on form when value changed", function() {
      var form = angular.element(directive.find("form"));
      var field = angular.element(directive.find("#key"));
      var newKey = makeName("new_key");
      changeFieldValue(field, newKey);
      expect(form.hasClass("saving")).toBe(true);
    });

    it("calls updateItem on form when value changed", function() {
      var field = angular.element(directive.find("#key"));
      var newKey = makeName("new_key");
      changeFieldValue(field, newKey);
      expect(updateItemMethod).toHaveBeenCalledWith({
        key: newKey
      });
    });

    it("doesnt call updateItem on form when no value change", function() {
      var field = angular.element(directive.find("#key"));
      changeFieldValue(field, $scope.obj.key);
      expect(updateItemMethod).not.toHaveBeenCalled();
    });

    it("removes 'saving' class on form when saved", function() {
      var form = angular.element(directive.find("form"));
      var field = angular.element(directive.find("#key"));
      var newKey = makeName("new_key");
      changeFieldValue(field, newKey);
      expect(form.hasClass("saving")).toBe(true);

      saveDefer.resolve($scope.obj);
      $scope.$digest();
      expect(form.hasClass("saving")).toBe(false);
    });

    it("updates the element to the value resolved", function() {
      var form = angular.element(directive.find("form"));
      var field = angular.element(directive.find("#key"));
      changeFieldValue(field, makeName("new_key"));
      expect(form.hasClass("saving")).toBe(true);

      var diffKey = makeName("diff_key");
      saveDefer.resolve({
        key: diffKey
      });
      $scope.$digest();
      expect(field.val()).toBe(diffKey);
    });

    it("sets string error on field", function() {
      var field = angular.element(directive.find("#key"));
      var control = angular.element(directive.find(".p-form__control"));
      changeFieldValue(field, makeName("new_key"));

      var error = makeName("error");
      saveDefer.reject(error);
      $scope.$digest();

      var errorsList = getErrorList(control);
      expect(errorsList).toEqual(["Error: " + error]);
    });

    it("sets field error on field", function() {
      var field = angular.element(directive.find("#key"));
      var control = angular.element(directive.find(".p-form__control"));
      changeFieldValue(field, makeName("new_key"));

      var error = makeName("error");
      saveDefer.reject(
        angular.toJson({
          key: error
        })
      );
      $scope.$digest();

      var errorsList = getErrorList(control);
      expect(errorsList).toEqual(["Error: " + error]);
      expect(control.hasClass("is-error")).toBe(true);
    });

    it("sets field error on another field", function() {
      var field = angular.element(directive.find("#key"));
      var control = angular.element(directive.find(".p-form__control"));
      changeFieldValue(field, makeName("new_key"));

      var error = makeName("error");
      saveDefer.reject(
        angular.toJson({
          otherKey: error
        })
      );
      $scope.$digest();

      var errorsList = getErrorList(control);
      expect(errorsList).toEqual(["Error: otherKey: " + error]);
      expect(control.hasClass("is-error")).toBe(true);
    });

    it("sets multiple errors on field", function() {
      var field = angular.element(directive.find("#key"));
      var control = angular.element(directive.find(".p-form__control"));
      changeFieldValue(field, makeName("new_key"));

      var error1 = makeName("error");
      var error2 = makeName("error");
      saveDefer.reject(
        angular.toJson({
          key: [error1, error2]
        })
      );
      $scope.$digest();

      var errList = getErrorList(control);
      expect(errList).toEqual(["Error: " + error1, "Error: " + error2]);
      expect(control.hasClass("is-error")).toBe(true);
    });
  });

  describe("preProcess", function() {
    it("calls function", function() {
      var preProcess = jasmine.createSpy();
      $scope.obj = {
        key: makeName("key")
      };
      $scope.process = preProcess;
      var saveDefer = $q.defer();
      var updateItemMethod = jasmine.createSpy();
      updateItemMethod.and.returnValue(saveDefer.promise);
      $scope.manager = {
        updateItem: updateItemMethod
      };
      var html = [
        '<maas-obj-form obj="obj" manager="manager" ',
        'pre-process="process">',
        '<maas-obj-field type="text" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "</maas-obj-form>"
      ].join("");
      var directive = compileDirective(html);
      var field = angular.element(directive.find("#key"));
      var newKey = makeName("new_key");
      changeFieldValue(field, newKey);
      expect(preProcess).toHaveBeenCalled();
    });
  });

  describe("multi fields", function() {
    var directive, updateItemMethod, saveDefer;
    beforeEach(function() {
      $scope.obj = {
        key1: makeName("key1"),
        key2: makeName("key2")
      };
      saveDefer = $q.defer();
      updateItemMethod = jasmine.createSpy();
      updateItemMethod.and.returnValue(saveDefer.promise);
      $scope.manager = {
        updateItem: updateItemMethod
      };
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="text" key="key1" label="Key1" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        '<maas-obj-field type="text" key="key2" label="Key2" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("sets field error on both fields", function() {
      var field1 = angular.element(directive.find("#key1"));
      var selector1 = "label[for='key1'] + .p-form__control";
      var selector2 = "label[for='key2'] + .p-form__control";
      var control1 = angular.element(directive.find(selector1));
      var control2 = angular.element(directive.find(selector2));
      changeFieldValue(field1, makeName("new_key"));

      var error1 = makeName("error");
      var error2 = makeName("error");
      saveDefer.reject(
        angular.toJson({
          key1: [error1],
          key2: [error2]
        })
      );
      $scope.$digest();

      expect(getErrorList(control1)).toEqual(["Error: " + error1]);
      expect(getErrorList(control2)).toEqual(["Error: " + error2]);
    });
  });

  describe("grouped fields", function() {
    var directive, updateItemMethod, saveDefer;
    beforeEach(function() {
      $scope.obj = {
        key1: makeName("key1"),
        key2: makeName("key2")
      };
      saveDefer = $q.defer();
      updateItemMethod = jasmine.createSpy();
      updateItemMethod.and.returnValue(saveDefer.promise);
      $scope.manager = {
        updateItem: updateItemMethod
      };
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        "<maas-obj-field-group>",
        '<maas-obj-field type="text" key="key1" label="Key1" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        '<maas-obj-field type="text" key="key2" label="Key2" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "</maas-obj-field-group>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("doesnt try to save when switching between fields", function() {
      var field1 = angular.element(directive.find("#key1"));
      var field2 = angular.element(directive.find("#key2"));
      changeFieldValue(field1, makeName("new_key"));
      field2.triggerHandler("focus");

      // Flush the all timers to make sure that save is not performed.
      $timeout.flush();

      expect(updateItemMethod).not.toHaveBeenCalled();
    });

    it("saves when both fields lose focus", function() {
      var field1 = angular.element(directive.find("#key1"));
      var field2 = angular.element(directive.find("#key2"));
      var newKey1 = makeName("new_key1");
      var newKey2 = makeName("new_key2");
      changeFieldValue(field1, newKey1);

      // Grab focus then flush to clear the timer from field1.
      field2.triggerHandler("focus");
      $scope.$digest();
      $timeout.flush();

      // Set the new value and lose focus.
      field2.val(newKey2);
      $scope.$digest();
      field2.triggerHandler("blur");
      $scope.$digest();

      // Flush the timer from field2 where save should be called.
      $timeout.flush();

      // Should be called with both fields set to the new value.
      expect(updateItemMethod).toHaveBeenCalledWith({
        key1: newKey1,
        key2: newKey2
      });
    });

    it("doesn't change field value when one being edited", function() {
      var field1 = angular.element(directive.find("#key1"));
      var field2 = angular.element(directive.find("#key2"));

      // Grab the focus of the first field.
      field1.triggerHandler("focus");
      $scope.$digest();

      // Change the value of field2 in the scope.
      var oldField2Value = $scope.obj.key2;
      var newField2Value = makeName("new_key2");
      $scope.obj.key2 = newField2Value;
      $scope.$digest();

      // Check that field2 still has the old value.
      expect(field2.val()).not.toBe(newField2Value);
      expect(field2.val()).toBe(oldField2Value);
    });
  });

  describe("disabled", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {};
      $scope.options = [
        {
          id: 0,
          text: "test"
        }
      ];
      $scope.disabled = false;
      var options = "option.id as option.text for option in options";
      var html = [
        '<maas-obj-form obj="obj" manager="manager" ' +
          'data-ng-disabled="disabled">',
        '<maas-obj-field type="text" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        '<maas-obj-field type="options" key="key2" label="Key 2" ',
        'placeholder="Placeholder 2" label-width="2" ',
        'input-width="3" options="' + options + '">',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("both input and select can be disabled", function() {
      var input = angular.element(directive.find("#key"));
      var select = angular.element(directive.find("#key2"));

      expect(input.prop("disabled")).toBe(false);
      expect(select.prop("disabled")).toBe(false);

      $scope.disabled = true;
      $scope.$digest();

      expect(input.prop("disabled")).toBe(true);
      expect(select.prop("disabled")).toBe(true);
    });
  });

  describe("afterSave", function() {
    it("calls function", function() {
      var afterSave = jasmine.createSpy("afterSave");
      $scope.obj = {
        key: makeName("key")
      };
      $scope.saved = afterSave;
      var saveDefer = $q.defer();
      var updateItemMethod = jasmine.createSpy();
      updateItemMethod.and.returnValue(saveDefer.promise);
      $scope.manager = {
        updateItem: updateItemMethod
      };
      var html = [
        '<maas-obj-form obj="obj" manager="manager" ',
        'after-save="saved">',
        '<maas-obj-field type="text" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "</maas-obj-form>"
      ].join("");
      var directive = compileDirective(html);
      var field = angular.element(directive.find("#key"));

      var newKey = makeName("new_key");
      changeFieldValue(field, newKey);

      saveDefer.resolve({
        key: newKey
      });
      $scope.$digest();
      expect(afterSave).toHaveBeenCalled();
    });
  });

  describe("tableForm", function() {
    it("adds form__group classes by default", function() {
      $scope.obj = {
        key: makeName("key")
      };
      $scope.manager = {};
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="text" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "</maas-obj-form>"
      ].join("");
      var directive = compileDirective(html);
      var group = angular.element(directive.find('maas-obj-field[key="key"]'));
      var field = angular.element(directive.find("#key"));
      expect(group.hasClass("p-form__group")).toBe(true);
      expect(field.parent("div").hasClass("p-form__control")).toBe(true);
    });
  });

  describe("form mode", function() {
    it("doesn't save on blur", function() {
      $scope.obj = {
        key: makeName("key")
      };
      var saveDefer = $q.defer();
      var updateItemMethod = jasmine.createSpy();
      updateItemMethod.and.returnValue(saveDefer.promise);
      $scope.manager = {
        updateItem: updateItemMethod
      };
      var html = [
        '<maas-obj-form obj="obj" manager="manager" ',
        'save-on-blur="false">',
        '<maas-obj-field type="text" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "</maas-obj-form>"
      ].join("");
      var directive = compileDirective(html);
      var field = angular.element(directive.find("#key"));

      var newKey = makeName("new_key");
      changeFieldValue(field, newKey);

      expect(updateItemMethod).not.toHaveBeenCalled();
    });

    it("saves on maasObjSave directive click", function() {
      $scope.obj = {
        key: makeName("key")
      };
      var saveDefer = $q.defer();
      var updateItemMethod = jasmine.createSpy();
      updateItemMethod.and.returnValue(saveDefer.promise);
      $scope.manager = {
        updateItem: updateItemMethod
      };
      var html = [
        '<maas-obj-form obj="obj" manager="manager" ',
        'save-on-blur="false">',
        '<maas-obj-field type="text" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "<button maas-obj-save></button>",
        "</maas-obj-form>"
      ].join("");
      var directive = compileDirective(html);
      var field = angular.element(directive.find("#key"));
      var button = angular.element(directive.find("button"));

      var newKey = makeName("new_key");
      changeFieldValue(field, newKey);

      // Not called on blur. Called on click of button.
      expect(updateItemMethod).not.toHaveBeenCalled();
      button.triggerHandler("click");
      expect(updateItemMethod).toHaveBeenCalledWith({
        key: newKey
      });
    });

    it("places global errors in maasObjErrors", function() {
      $scope.obj = {
        key: makeName("key")
      };
      var saveDefer = $q.defer();
      var updateItemMethod = jasmine.createSpy();
      updateItemMethod.and.returnValue(saveDefer.promise);
      $scope.manager = {
        updateItem: updateItemMethod
      };
      var html = [
        '<maas-obj-form obj="obj" manager="manager" ',
        'save-on-blur="false">',
        '<maas-obj-field type="text" key="key" label="Key" ',
        'placeholder="Placeholder" label-width="2" ',
        'input-width="3"></maas-obj-field>',
        "<maas-obj-errors></maas-obj-errors>",
        "<button maas-obj-save></button>",
        "</maas-obj-form>"
      ].join("");
      var directive = compileDirective(html);
      var field = angular.element(directive.find(".p-form__group"));
      var errors = angular.element(directive.find("maas-obj-errors"));
      var button = angular.element(directive.find("button"));

      var newKey = makeName("new_key");
      changeFieldValue(field, newKey);
      button.triggerHandler("click");

      var error = makeName("error");
      var keyError = makeName("keyError");
      saveDefer.reject(
        angular.toJson({
          __all__: [error],
          key: [keyError]
        })
      );
      $scope.$digest();

      // Error is placed on the input and in the global section.
      expect(getErrorList(field)).toEqual(["Error: " + keyError]);
      expect(getErrorList(errors)).toEqual([" " + error]);

      // Has error returns true.
      expect($scope.obj.$maasForm.hasErrors()).toBe(true);
    });
  });

  describe("disableLabel", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {};
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="text" key="key" ' +
          'disable-label="true"></maas-obj-field>',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("label is not added", function() {
      var label = directive.find("label");
      expect(label.length).toBe(0);
    });
  });

  describe("labelInfo", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {};
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="text" key="key" ' +
          'label-info="My Info"></maas-obj-field>',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("icon add with tooltip added in label", function() {
      var label = directive.find("label");
      var icon = label.find("i");
      var tooltip = directive.find("span");
      var tooltipMessage = directive.find(".p-tooltip__message");
      expect(label.text()).toContain("key");
      expect(icon.hasClass("p-icon--information")).toBe(true);
      expect(tooltip.attr("class")).toContain("p-tooltip--");
      expect(tooltipMessage.text()).toBe("My Info");
    });

    it("should call preventDefault on click", function() {
      const event = {
        preventDefault: () => {},
        type: "click"
      };
      jest.spyOn(event, "preventDefault");
      var label = directive.find("label");
      var icon = label.find("i");
      icon.triggerHandler(event);
      expect(event.preventDefault).toHaveBeenCalled();
    });
  });

  describe("labelLeft", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {};
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="text" key="key" ' +
          'label-info="My Info" ' +
          'label-left="true"></maas-obj-field>',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("icon add with tooltip added in label", function() {
      var label = directive.find("label");
      var icon = label.find("i");
      var p = label.find("p");
      expect(label.contents().get(0).nodeValue).toBe("key");
      expect(icon.hasClass("p-icon--information")).toBe(true);
      expect(p.hasClass("p-tooltip__message")).toBe(true);
      expect(p.text()).toBe("My Info");
    });

    it("should call preventDefault on click", function() {
      const event = {
        preventDefault: () => {},
        type: "click"
      };
      jest.spyOn(event, "preventDefault");
      var label = directive.find("label");
      var icon = label.find("i");
      icon.triggerHandler(event);
      expect(event.preventDefault).toHaveBeenCalled();
    });
  });

  describe("inputClass", function() {
    var directive;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {};
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<maas-obj-field type="text" key="key" ' +
          'input-class="new-class"></maas-obj-field>',
        "</maas-obj-field>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("input-class is added", function() {
      var input = angular.element(directive.find("input"));
      expect(input.hasClass("new-class")).toBe(true);
    });
  });

  describe("unregisterField", function() {
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {};
      $scope.show = true;
      var html = [
        '<maas-obj-form obj="obj" manager="manager">',
        '<div data-ng-if="show">',
        '<maas-obj-field type="text" key="key" ' +
          'input-class="new-class"></maas-obj-field>',
        "</maas-obj-field>",
        "</div>",
        "</maas-obj-form>"
      ].join("");
      compileDirective(html);
    });

    it("fields is unregistered when removed", function() {
      expect($scope.obj.$maasForm.fields.key).toBeDefined();
      $scope.show = false;
      $scope.$digest();
      expect($scope.obj.$maasForm.fields.key).toBeUndefined();
    });
  });

  describe("maasObjSaving", function() {
    var directive, defer;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {
        updateItem: jasmine.createSpy("updateItem")
      };
      defer = $q.defer();
      $scope.manager.updateItem.and.returnValue(defer.promise);
      var html = [
        '<maas-obj-form obj="obj" manager="manager" ',
        'save-on-blur="false">',
        '<maas-obj-field type="text" key="key" ' +
          'input-class="new-class"></maas-obj-field>',
        "</maas-obj-field>",
        "<button maas-obj-save>Save</button>",
        "<maas-obj-saving>Test saving</maas-obj-saving>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("shows spinner and text when saving", function() {
      var saveBtn = directive.find("button[maas-obj-save]");
      var spinner = directive.find("maas-obj-saving").find("i");
      expect(spinner.length).toBe(0);

      saveBtn.click();
      spinner = directive.find("maas-obj-saving").find("i");
      expect(spinner.length).toBe(1);
      var text = directive
        .find("maas-obj-saving")
        .find("span[data-ng-transclude]");
      expect(text.text()).toBe("Test saving");

      defer.resolve({});
      $scope.$digest();
      spinner = directive.find("maas-obj-saving").find("i");
      expect(spinner.length).toBe(0);
    });
  });

  describe("maasObjShowSaving", function() {
    var directive, defer;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {
        updateItem: jasmine.createSpy("updateItem")
      };
      defer = $q.defer();
      $scope.manager.updateItem.and.returnValue(defer.promise);
      var html = [
        '<maas-obj-form obj="obj" manager="manager" ',
        'save-on-blur="false">',
        '<maas-obj-field type="text" key="key" ' +
          'input-class="new-class"></maas-obj-field>',
        "</maas-obj-field>",
        "<button maas-obj-save>Save</button>",
        "<div maas-obj-show-saving></div>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("sets ng-hide initially", function() {
      var testElem = directive.find("div[maas-obj-show-saving]");
      expect(testElem.hasClass("ng-hide")).toBe(true);
    });

    it("removes ng-hide when saving", function() {
      var saveBtn = directive.find("button[maas-obj-save]");
      saveBtn.click();

      var testElem = directive.find("div[maas-obj-show-saving]");
      expect(testElem.hasClass("ng-hide")).toBe(false);
    });

    it("removes ng-hide when done saving", function() {
      var saveBtn = directive.find("button[maas-obj-save]");
      saveBtn.click();
      defer.resolve({});
      $scope.$digest();

      var testElem = directive.find("div[maas-obj-show-saving]");
      expect(testElem.hasClass("ng-hide")).toBe(true);
    });
  });

  describe("maasObjHideSaving", function() {
    var directive, defer;
    beforeEach(function() {
      $scope.obj = {};
      $scope.manager = {
        updateItem: jasmine.createSpy("updateItem")
      };
      defer = $q.defer();
      $scope.manager.updateItem.and.returnValue(defer.promise);
      var html = [
        '<maas-obj-form obj="obj" manager="manager" ',
        'save-on-blur="false">',
        '<maas-obj-field type="text" key="key" ' +
          'input-class="new-class"></maas-obj-field>',
        "</maas-obj-field>",
        "<button maas-obj-save>Save</button>",
        "<div maas-obj-hide-saving></div>",
        "</maas-obj-form>"
      ].join("");
      directive = compileDirective(html);
    });

    it("no ng-hide initially", function() {
      var testElem = directive.find("div[maas-obj-hide-saving]");
      expect(testElem.hasClass("ng-hide")).toBe(false);
    });

    it("adds ng-hide when saving", function() {
      var saveBtn = directive.find("button[maas-obj-save]");
      saveBtn.click();

      var testElem = directive.find("div[maas-obj-hide-saving]");
      expect(testElem.hasClass("ng-hide")).toBe(true);
    });

    it("no ng-hide when done saving", function() {
      var saveBtn = directive.find("button[maas-obj-save]");
      saveBtn.click();
      defer.resolve({});
      $scope.$digest();

      var testElem = directive.find("div[maas-obj-hide-saving]");
      expect(testElem.hasClass("ng-hide")).toBe(false);
    });
  });
});
