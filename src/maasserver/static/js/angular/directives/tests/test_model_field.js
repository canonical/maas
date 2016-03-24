/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for MAAS model field directive.
 */

describe("maasModelField", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Create a new scope before each test.
    var $scope;
    beforeEach(inject(function($rootScope) {
        $scope = $rootScope.$new();
    }));

    // Load a couple of managers to test with.
    var FabricsManager, VLANsManager;
    beforeEach(inject(function($injector) {
        FabricsManager = $injector.get("FabricsManager");
        VLANsManager = $injector.get("VLANsManager");
    }));

    // Return the compiled directive with the items from the scope.
    function compileDirective(field, labelClass, selectClass, inputTextClass) {
        var directive = null;
        var element = angular.element('<div />').
            attr('data-maas-model-field', field);
        if(angular.isString(labelClass)) {
            element.attr('data-maas-label-class', labelClass);
        }
        if(angular.isString(selectClass)) {
            element.attr('data-maas-select-class', selectClass);
        }
        if(angular.isString(inputTextClass)) {
            element.attr('data-maas-input-text-class', inputTextClass);
        }
        var html = element[0].outerHTML;

        // Compile the directive.
        inject(function($compile) {
            directive = $compile(html)($scope);
        });

        // Perform the digest cycle to finish the compile.
        $scope.$digest();
        return directive;
    }

    it("omits fields marked omittted", function() {
        var field = {
            omit: true
        };
        var expectedName = "field_title";
        $scope.field = field;
        var directive = compileDirective("field");
        var generated = directive.children();
        var iscope = directive.isolateScope();
        expect(iscope.item).toBe(field);
        expect(generated.length).toBe(0);
    });

    it("renders basic field with label", function() {
        var field = {
            title: "Field Title"
        };
        var expectedName = "field_title";
        $scope.field = field;
        var directive = compileDirective("field");
        var generated = directive.children();
        var iscope = directive.isolateScope();
        expect(iscope.item).toBe(field);
        expect(generated.length).toBe(2);
        // We expect the first child to be the <label/>
        var label = angular.element(generated[0]);
        expect(label.prop('tagName')).toEqual("LABEL");
        expect(label.attr('for')).toEqual(expectedName);
        expect(label.text()).toEqual(field.title);
        // We expect the next child to be the <div/>
        var div = angular.element(generated[1]);
        expect(div.prop('tagName')).toEqual("DIV");
        var divChildren = div.children();
        expect(divChildren.length).toBe(1);
        // We expect the <div/> to contain the input field.
        var input = angular.element(divChildren[0]);
        expect(input.prop('tagName')).toEqual("INPUT");
        expect(input.attr('type')).toEqual("text");
        expect(input.attr('name')).toEqual(expectedName);
        expect(input.attr('id')).toEqual(expectedName);
    });

    it("renders basic field with label and placeholder", function() {
        var field = {
            title: "Field Title",
            placeholder: "Enter the Thing"
        };
        var expectedName = "field_title";
        $scope.field = field;
        var directive = compileDirective("field");
        var generated = directive.children();
        var iscope = directive.isolateScope();
        expect(iscope.item).toBe(field);
        expect(generated.length).toBe(2);
        // We expect the first child to be the <label/>
        var label = angular.element(generated[0]);
        expect(label.prop('tagName')).toEqual("LABEL");
        expect(label.attr('for')).toEqual(expectedName);
        expect(label.text()).toEqual(field.title);
        // We expect the next child to be the <div/>
        var div = angular.element(generated[1]);
        expect(div.prop('tagName')).toEqual("DIV");
        var divChildren = div.children();
        expect(divChildren.length).toBe(1);
        // We expect the <div/> to contain the input field.
        var input = angular.element(divChildren[0]);
        expect(input.prop('tagName')).toEqual("INPUT");
        expect(input.attr('type')).toEqual("text");
        expect(input.attr('name')).toEqual(expectedName);
        expect(input.attr('id')).toEqual(expectedName);
        expect(input.attr('placeholder')).toEqual(field.placeholder);
    });

    it("renders basic field with custom css", function() {
        var field = {
            title: "Field Title"
        };
        $scope.field = field;
        var directive = compileDirective(
            "field", "labelClass", null, "inputClass");
        var generated = directive.children();
        var iscope = directive.isolateScope();
        expect(iscope.item).toBe(field);
        expect(generated.length).toBe(2);
        // We expect the first child to be the <label/>
        var label = angular.element(generated[0]);
        expect(label.prop('tagName')).toEqual("LABEL");
        expect(label.hasClass("labelClass")).toBe(true);
        // We expect the next child to be the <div/>
        var div = angular.element(generated[1]);
        expect(div.prop('tagName')).toEqual("DIV");
        expect(div.hasClass('inputClass')).toBe(true);
    });

    it("renders basic field with default css", function() {
        var field = {
            title: "Field Title"
        };
        $scope.field = field;
        var directive = compileDirective("field");
        var generated = directive.children();
        var iscope = directive.isolateScope();
        expect(iscope.item).toBe(field);
        expect(generated.length).toBe(2);
        // We expect the first child to be the <label/>
        var label = angular.element(generated[0]);
        expect(label.prop('tagName')).toEqual("LABEL");
        expect(label.hasClass("two-col")).toBe(true);
        // We expect the next child to be the <div/>
        var div = angular.element(generated[1]);
        expect(div.prop('tagName')).toEqual("DIV");
        expect(div.hasClass('three-col')).toBe(true);
        expect(div.hasClass('last-col')).toBe(true);
    });

    it("renders select field with custom css", function() {
        var field = {
            title: "Field Title",
            manager: VLANsManager
        };
        $scope.field = field;
        var directive = compileDirective(
            "field", "labelClass", "selectClass");
        var generated = directive.children();
        var iscope = directive.isolateScope();
        expect(iscope.item).toBe(field);
        expect(generated.length).toBe(2);
        // We expect the first child to be the <label/>
        var label = angular.element(generated[0]);
        expect(label.prop('tagName')).toEqual("LABEL");
        expect(label.hasClass("labelClass")).toBe(true);
        // We expect the next child to be the <div/>
        var div = angular.element(generated[1]);
        expect(div.prop('tagName')).toEqual("DIV");
        expect(div.hasClass('selectClass')).toBe(true);
    });

    it("renders select field with default css", function() {
        var field = {
            title: "Field Title",
            manager: VLANsManager
        };
        $scope.field = field;
        var directive = compileDirective("field");
        var generated = directive.children();
        var iscope = directive.isolateScope();
        expect(iscope.item).toBe(field);
        expect(generated.length).toBe(2);
        // We expect the first child to be the <label/>
        var label = angular.element(generated[0]);
        expect(label.prop('tagName')).toEqual("LABEL");
        expect(label.hasClass("two-col")).toBe(true);
        // We expect the next child to be the <div/>
        var div = angular.element(generated[1]);
        expect(div.prop('tagName')).toEqual("DIV");
        expect(div.hasClass('three-col')).toBe(true);
        expect(div.hasClass('last-col')).toBe(true);
    });

    it("renders select field with correct ng-options", function() {
        VLANsManager._items.push({
            id: 0,
            vid: 0,
            fabric: 0
        });
        VLANsManager._items.push({
            id: 1,
            vid: 100,
            fabric: 0
        });
        var field = {
            title: "Field Title",
            manager: VLANsManager
        };
        $scope.field = field;
        var directive = compileDirective("field");
        var generated = directive.children();
        var iscope = directive.isolateScope();
        expect(iscope.item).toBe(field);
        expect(generated.length).toBe(2);
        // We expect the first child to be the <label/>
        var label = angular.element(generated[0]);
        expect(label.prop('tagName')).toEqual("LABEL");
        // We expect the next child to be the <div/>
        var div = angular.element(generated[1]);
        expect(div.prop('tagName')).toEqual("DIV");
        // We expect the <div/> to contain the input field.
        var divChildren = div.children();
        var select = angular.element(divChildren[0]);
        expect(select.prop('tagName')).toEqual("SELECT");
        expect(select.attr('data-ng-options')).toEqual(
            "obj[item.manager._pk] as item.manager.getName(obj) " +
            "for obj in items");
    });

    it("renders select field with placeholder if desired", function() {
        VLANsManager._items.push({
            id: 0,
            vid: 0,
            fabric: 0
        });
        VLANsManager._items.push({
            id: 1,
            vid: 100,
            fabric: 0
        });
        var field = {
            title: "Field Title",
            manager: VLANsManager,
            placeholder: "We like placeholders."
        };
        $scope.field = field;
        var directive = compileDirective("field");
        var generated = directive.children();
        var iscope = directive.isolateScope();
        expect(iscope.item).toBe(field);
        expect(generated.length).toBe(2);
        // We expect the first child to be the <label/>
        var label = angular.element(generated[0]);
        expect(label.prop('tagName')).toEqual("LABEL");
        // We expect the next child to be the <div/>
        var div = angular.element(generated[1]);
        expect(div.prop('tagName')).toEqual("DIV");
        // We expect the <div/> to contain the input field.
        var divChildren = div.children();
        var select = angular.element(divChildren[0]);
        expect(select.prop('tagName')).toEqual("SELECT");
        var option = angular.element(select.children()[0]);
        expect(option.prop('tagName')).toEqual("OPTION");
        expect(option.attr('value')).toEqual('');
        expect(option.attr('disabled')).toEqual('disabled');
        expect(option.attr('hidden')).toEqual('hidden');
        expect(option.text()).toEqual(field.placeholder);
    });

    it("renders select field with correct ng-options", function() {
        FabricsManager._items.push({
            id: 0,
            name: "fabric-0"
        });

        VLANsManager._items.push({
            id: 0,
            vid: 0,
            fabric: 0
        });
        VLANsManager._items.push({
            id: 1,
            vid: 100,
            fabric: 0
        });
        var field = {
            title: "Field Title",
            manager: VLANsManager,
            groupReference: "fabric",
            group: FabricsManager
        };
        $scope.field = field;
        var directive = compileDirective("field");
        var generated = directive.children();
        var iscope = directive.isolateScope();
        expect(iscope.item).toBe(field);
        expect(generated.length).toBe(2);
        // We expect the first child to be the <label/>
        var label = angular.element(generated[0]);
        expect(label.prop('tagName')).toEqual("LABEL");
        // We expect the next child to be the <div/>
        var div = angular.element(generated[1]);
        expect(div.prop('tagName')).toEqual("DIV");
        // We expect the <div/> to contain the input field.
        var divChildren = div.children();
        var select = angular.element(divChildren[0]);
        expect(select.prop('tagName')).toEqual("SELECT");
        expect(select.attr('data-ng-options')).toEqual(
            "obj[item.manager._pk] as item.manager.getName(obj) " +
            "group by item.group.getName(" +
                "item.group.getItemFromList(obj.fabric)) " +
            "for obj in items");
    });

});
