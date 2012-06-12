/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.node_add.tests', function(Y) {

Y.log('loading maas.node_add.tests');
var namespace = Y.namespace('maas.node_add.tests');

var module = Y.maas.node_add;
var suite = new Y.Test.Suite("maas.node_add Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-node-add-widget-singleton',

    setUp: function() {
        // Silence io.
        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'send',
            args: [MAAS_config.uris.nodes_handler, Y.Mock.Value.Any]
        });
        this.mockIO(mockXhr, module);
    },

    testSingletonCreation: function() {
        // module._add_node_singleton is originally null.
        Y.Assert.isNull(module._add_node_singleton);
        module.showAddNodeWidget({targetNode: '#target_node', animate: false});
        // module._add_node_singleton is populated after the call to
        // module.showAddNodeWidget.
        Y.Assert.isNotNull(module._add_node_singleton);
    },

    testSingletonReCreation: function() {
        module.showAddNodeWidget({targetNode: '#target_node', animate: false});
        var panel = module._add_node_singleton;

        // Make sure that a second call to showAddNodeWidget destroys
        // the old widget and creates a new one.
        var destroyed = false;
        panel.on("destroy", function(){
            destroyed = true;
        });
        module.showAddNodeWidget({targetNode: '#target_node', animate: false});
        Y.Assert.isTrue(destroyed);
        Y.Assert.isNotNull(module._add_node_singleton);
        Y.Assert.areNotSame(panel, namespace._add_node_singleton);
    }

}));


/* Find the add-node widget.
 */
function find_widget() {
    return module._add_node_singleton.get('srcNode');
}


/* Find the add-node form.
 */
function find_form() {
    return find_widget().one('form');
}


/* Find the hostname input field in the add-node form.
 */
function find_hostname_input() {
    return find_widget().one('#id_hostname');
}


/* Find the "Add node" button at the bottom of the add-node form.
 */
function find_add_button() {
    return find_widget().one('.add-node-button');
}


/* Find the global errors panel at the top of the add-node form.
 */
function find_global_errors() {
    return find_widget().one('.form-errors');
}


/* Set up and submit the add-node form.
 */
function submit_add_node() {
    module.showAddNodeWidget({targetNode: '#target_node', animate: false});
    find_hostname_input().set('value', 'host');
    find_add_button().simulate('click');
}


suite.add(new Y.maas.testing.TestCase({
    name: 'test-add-node-widget-add-node',

    testFormContainsArchitectureChoice: function() {
        // The generated form contains an 'architecture' field.
        module.showAddNodeWidget({targetNode: '#target_node', animate: false});
        var arch = find_form().one('#id_architecture');
        Y.Assert.isNotNull(arch);
        var arch_options = arch.all('option');
        Y.Assert.areEqual(2, arch_options.size());
     },

    testAddNodeAPICallSubmitsForm: function() {
        // The call to the API triggered by clicking on 'Add a node'
        // submits (via an API call) the panel's form.
        module.showAddNodeWidget({targetNode: '#target_node', animate: false});
        var mockXhr = new Y.Base();
        var form = find_form();
        var log = this.logIO(module);
        find_hostname_input().set('value', 'host');
        find_add_button().simulate('click');
        Y.Assert.areEqual(form, log.pop()[1].form.id);
    },

    testAddNodeAPICall: function() {
        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'send',
            args: [MAAS_config.uris.nodes_handler, Y.Mock.Value.Any]
        });
        this.mockIO(mockXhr, module);
        module.showAddNodeWidget({targetNode: '#target_node', animate: false});
        find_hostname_input().set('value', 'host');
        find_add_button().simulate('click');
        Y.Mock.verify(mockXhr);
    },

    testAddNodeAPICallEnterPressed: function() {
        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'send',
            args: [MAAS_config.uris.nodes_handler, Y.Mock.Value.Any]
        });
        this.mockIO(mockXhr, module);
        module.showAddNodeWidget({targetNode: '#target_node', animate: false});
        find_hostname_input().set('value', 'host');
        // Simulate 'Enter' being pressed.
        find_form().simulate("keypress", { keyCode: 13 });
        Y.Mock.verify(mockXhr);
    },

    testNodeidPopulation: function() {
        this.mockSuccess(Y.JSON.stringify({system_id: 3}), module);
        module.showAddNodeWidget({targetNode: '#target_node', animate: false});
        this.addCleanup(
            Y.bind(
                module._add_node_singleton.destroy,
                module._add_node_singleton));
        find_hostname_input().set('value', 'host');
        var button = find_add_button();

        var fired = false;
        this.registerListener(
            Y.maas.node_add.AddNodeDispatcher, module.NODE_ADDED_EVENT,
            function(e, node){
                Y.Assert.areEqual(3, node.system_id);
                fired = true;
            }
        );
        button.simulate('click');
        Y.Assert.isTrue(fired);
    },

    testValidationErrorInJSONGoesToFieldsNotGlobalErrors: function() {
        this.mockFailure('{"architecture": ["Xur."]}', module, 400);
        submit_add_node();
        Y.Assert.areEqual(
            -1, find_global_errors().get('innerHTML').search("Xur."));
        var field_label = find_widget().one('label[for="id_architecture"]');
        var error_node = field_label.next();
        Y.Assert.areNotEqual(-1, error_node.get('innerHTML').search("Xur."));
    },

    test400ErrorMessageWithPlainText: function() {
        this.mockFailure("Blergh.", module, 400);
        submit_add_node();
        var error_message = find_global_errors().get('innerHTML');
        Y.Assert.areNotEqual(-1, error_message.search("Blergh."));
    },

    testLoggedOffErrorMessage: function() {
        this.mockFailure("You are not logged in.", module, 401);
        submit_add_node();
        var error_message = find_global_errors().get('innerHTML');
        // The link to the login page is present in the error message.
        var link_position = error_message.search(MAAS_config.uris.login);
        Y.Assert.areNotEqual(-1, link_position);
    },

    testGenericErrorMessage: function() {
        this.mockFailure("Internal error.", module, 500);
        submit_add_node();
        var error_message = find_global_errors().get('innerHTML');
        Y.Assert.areNotEqual(-1, error_message.search("Internal error."));
    },

    testErrorsAreEscaped: function() {
        this.mockFailure("<huh>", module, 400);
        submit_add_node();
        var error_message = find_global_errors().get('innerHTML');
        Y.Assert.areEqual(-1, error_message.search("<huh>"));
        Y.Assert.areNotEqual(-1, error_message.search("&lt;huh&gt;"));
    }

}));

suite.add(new Y.maas.testing.TestCase({
    name: 'test-add-node-widget-add-node-admin',

    setUp: function() {
        this.setUpAdminTemplate();
        this.setUpPowerTypeEnum();
    },

    setUpPowerTypeEnum: function() {
        // Override module.POWER_TYPE_ENUM for the sake of testing.
        this.POWER_TYPE_ENUM = module.POWER_TYPE_ENUM;
        module.POWER_TYPE_ENUM = ENUM;
    },

    setUpAdminTemplate: function() {
        // Append the snippet that will be seen by an admin user to the
        // general template.
        this.add_node_template = Y.one('#add-node').getContent();
        this.add_node_admin_snippet = Y.one('#add-node-admin').getContent();
        Y.one('#add-node').set(
            'innerHTML',
            this.add_node_template + this.add_node_admin_snippet);
    },

    tearDown: function() {
        this.tearDownAdminTemplate();
        this.tearDownPowerTypeEnum();
    },

    tearDownAdminTemplate: function() {
        Y.one('#add-node').set('innerHTML', this.add_node_template);
    },

    tearDownPowerTypeEnum: function() {
        module.POWER_TYPE_ENUM = this.POWER_TYPE_ENUM;
    },

    testFormContainsPowerType: function() {
        module.showAddNodeWidget({targetNode: '#target_node', animate: false});
        Y.Assert.isNotNull(find_widget().one('#id_power_type'));
    },

    testPowerParameterHidden: function() {
        // The power_parameter field starts hidden.
        module.showAddNodeWidget({targetNode: '#target_node', animate: false});
        Y.Assert.isTrue(
            find_widget().one('.power_parameters').hasClass('hidden'));
    },

    testPowerParameterDynamicallyLinked: function() {
        // When the option of the 'select' tag changes to a non empty
        // string, the 'power_parameters' field is shown.
        module.showAddNodeWidget({targetNode: '#target_node', animate: false});
        var select = Y.one('#id_power_type');
        select.set('value', 'value1');
        select.simulate('change');
        Y.Assert.isFalse(
            find_widget().one('.power_parameters').hasClass('hidden'));
    }


}));


namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.node_add']}
);
