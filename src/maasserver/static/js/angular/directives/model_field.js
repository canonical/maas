/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Directive to create a label and corresponding input field.
 */

angular.module('MAAS').directive(
    'maasModelField', ['$compile', function($compile) {

    // Returns a <label/> for the specified item.
    function buildInputLabel(item, classes) {
        var label = angular.element('<label />')
            .attr('class', classes.label)
            .attr('for', item.name)
            .text(item.title);
        return label;
    }

    // Returns a <select/> for the specified item, with a single <option/>
    // placeholder and a <div/> wrapping it for CSS purposes.
    function buildInputSelectField(item, classes) {
        // Construct the options expression, based on whether or not a
        // group by was specified.
        var ngOptions = 'obj[item.manager._pk] as item.manager.getName(obj) ';
        if(angular.isObject(item.group) &&
            angular.isString(item.groupReference)) {
            // For the group by string, we need to go to the manager for each
            // group and grab the name of the item, based on the the primary
            // key field given in groupReference.
            ngOptions +=
                'group by item.group.getName(' +
                'item.group.getItemFromList(' +
                    'obj.' + item.groupReference +')) ';
        }
        ngOptions += 'for obj in items';
        // Construct a <select/>, which will be bound to the
        // $scope upon $compile().
        var select = angular.element('<select />')
            .attr('name', item.name)
            .attr('data-ng-model', 'item.current')
            .attr('data-ng-options', ngOptions);
        // If the user provided a default item, initialize the item with it.
        // (This must be the ID of the desired item.)
        if(item.defaultItem !== undefined) {
            select.attr('data-ng-init', 'item.current = ' + item.defaultItem);
        }
        // Construct a placeholder option. This option will not
        // appear in the <select/> list; rather, it is an
        // indication to the user that they still need to select
        // a valid option.
        if(angular.isString(item.placeholder)) {
            var placeholder = angular.element('<option />')
                .attr('value', '')
                .attr('disabled', '')
                .attr('hidden', '')
                .text(item.placeholder);
            // Add the placeholder option to the <select/>.
            select.html(placeholder);
        }
        var div = angular.element("<div />")
            .attr('class', classes.select);
        // Wrap the field in a <div/> for CSS purposes.
        div.html(select);
        return div;
    }

    // Returns an <input type="text"/> field for the specified item,
    // wrapped with a <div/> for CSS purposes.
    function buildInputTextField(item, classes) {
        var input = angular.element('<input />')
            .attr('type', 'text')
            .attr('name', item.name)
            .attr('id', item.name)
            .attr('data-ng-model', 'item.current');
        if(angular.isString(item.placeholder)) {
            input.attr('placeholder', item.placeholder);
        }
        var div = angular.element("<div />")
            .attr('class', classes.inputText);
        // Wrap the field in a <div/> for CSS purposes.
        div.html(input);
        return div;
    }

    function parseClassAttributes(attributes) {
        // Default CSS classes.
        var classes = {
            label: "two-col",
            select: "three-col last-col",
            inputText: "three-col last-col"
        };
        if(angular.isObject(attributes)) {
            if(angular.isString(attributes.maasLabelClass)) {
                classes.label = attributes.maasLabelClass;
            }
            if(angular.isString(attributes.maasSelectClass)) {
                classes.select = attributes.maasSelectClass;
            }
            if(angular.isString(attributes.maasInputTextClass)) {
                classes.inputText = attributes.maasInputTextClass;
            }
        }
        return classes;
    }

    // Builds an input field for the specified item. Returns an HTML element
    // that can be appended to the DOM.
    function buildInputField(item, classes) {
       if(angular.isObject(item.manager)) {
            return buildInputSelectField(item, classes);
        } else {
            return buildInputTextField(item, classes);
        }
    }

    return {
        restrict: "A",
        require: "maasModelField",
        scope: {
            item: '=maasModelField'
        },
        compile: function(element, attrs) {
            return {
                post: function(scope, element, attrs) {
                    var item = scope.item;
                    // If the feature is flagged as omitted in the data model,
                    // don't bother building up anything to append to the DOM.
                    if(item.omit === true) {
                        return;
                    }
                    var classes = parseClassAttributes(attrs);
                    var label = buildInputLabel(item, classes);
                    var field = buildInputField(item, classes);
                    // Place the label and input fields into the DOM.
                    element.append(label).append(field);
                    $compile(element.contents())(scope);
                }
            };
        },
        controller: function ($scope) {
            var item = $scope.item;
            // If the caller didn't supply a name field, just derive one
            // from the title. (Convert it to all-lowercase, and replace any
            // spaces with underscores.) This is done so that the JSON objects
            // are more DRY.
            if(item.omit === true) {
                return;
            }
            if(!angular.isString(item.name)) {
                item.name = item.title.toLowerCase().split(' ').join('_');
            }
            item.current = null;
            if(angular.isObject(item.manager)) {
                $scope.items = item.manager.getItems();
            }
        }
    };
}]);

