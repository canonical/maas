/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI().add('maas.testing', function(Y) {

Y.log('loading mass.testing');

var module = Y.namespace('maas.testing');

module.TestCase = Y.Base.create('ioMockableTestCase', Y.Test.Case, [], {

    _setUp: function() {
        if (!Y.Lang.isValue(this._cleanups)) {
            this._cleanups = [];
        }
    },

    addCleanup: function(func) {
        this._setUp();
        this._cleanups.push(func);
    },

    tearDown: function() {
        this._setUp();
        var func;
        while (func = this._cleanups.pop()) { func(); }
    },

   /**
    * Mock the '_io' field of the provided module.  This assumes that
    * the module has a internal reference to its io module named '_io'
    * and that all its io is done via module._io.io(...).
    *
    * @method mockIO
    * @param mock the mock object that should replace the module's io
    * @param module the module to monkey patch
    */
    mockIO: function(mock, module) {
        var io = module._io;
        module._io = mock;
        this.addCleanup(function() { module._io = io; });
    },

   /**
    * Register a method to be fired when the event 'name' is triggered on
    * 'source'.  The handle will be cleaned up when the test finishes.
    *
    * @method registerListener
    * @param source the source of the event
    * @param name the name of the event to listen to
    * @param method the method to run
    * @param context the context in which the method should be run
    */
    registerListener: function(source, name, method, context) {
        var handle = source.on(name, method, context);
        this.addCleanup(Y.bind(handle.detach, handle));
        return handle;
    },

    mockSuccess: function(response, module) {
        var mockXhr = {};
        mockXhr.io = function(url, cfg) {
           var out = {};
           out.response = response;
           cfg.on.success('4', out);
        };
        this.mockIO(mockXhr, module);
    }

});

}, '0.1', {'requires': ['test', 'base']}
);
