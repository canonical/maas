/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI().add('maas.testing', function(Y) {

Y.log('loading maas.testing');

var module = Y.namespace('maas.testing');


/**
 * Create a fake http response.
 */
function make_fake_response(response_text, status_code) {
    var out = {};
    // status_code defaults to undefined, since it's not always set.
    if (Y.Lang.isValue(status_code)) {
        out.status = status_code;
    }
    out.responseText = response_text;

    /* We probably shouldn't rely on the response attribute: according to
     * http://yuilibrary.com/yui/docs/io/#the-response-object it doesn't
     * always have to be populated.  We do get a guarantee for responseText
     * or responseXML.
     */
    out.response = response_text;

    return out;
}


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
        while (this._cleanups.length) {
            this._cleanups.pop()();
        }
    },

   /**
    * Mock the '_io' field of the provided module.  This assumes that
    * the module has a internal reference to its io module named '_io'.
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
    * Mock the '_io' field of the provided module with a silent method that
    * simply records the call to 'send'.  Returns an array where calls will
    * be recorded.
    * This assumes that the module has a internal reference to its io module
    * named '_io' and that all its io is done via module._io.send(...).
    *
    * @method logIO
    * @param module the module to monkey patch
    */
    logIO: function(module) {
        var log = [];
        var mockXhr = new Y.Base();
        mockXhr.send = function(url, cfg) {
            log.push([url, cfg]);
        };
        this.mockIO(mockXhr, module);
        return log;
    },

   /**
    * Mock the '_io' field to silence io.
    * This assumes that the module has a internal reference to its io module
    * named '_io' and that all its io is done via module._io.send(...).
    *
    * @method silentIO
    * @param module the module to monkey patch
    */
    silentIO: function(module) {
        var mockXhr = new Y.Base();
        mockXhr.send = function(url, cfg) {
        };
        this.mockIO(mockXhr, module);
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

    /**
     * Set up mockIO to feign successful I/O completion.  Returns an array
     * where calls will be recorded.
     *
     * @method mockSuccess
     * @param response_text The response text to fake.  It will be available
     *     as request.responseText in the request passed to the success
     *     handler.
     * @param module The module to be instrumented.
     * @param status_code Optional HTTP status code.  This defaults to
     *     undefined, since the attribute may not always be available.
     */
    mockSuccess: function(response_text, module, status_code) {
        var log = [];
        var mockXhr = new Y.Base();
        mockXhr.send = function(url, cfg) {
            log.push([url, cfg]);
            var response = make_fake_response(response_text, status_code);
            var arbitrary_txn_id = '4';
            cfg.on.success(arbitrary_txn_id, response);
        };
        this.mockIO(mockXhr, module);
        return log;
    },

    /**
     * Set up mockIO to feign I/O failure.  Returns an array
     * where calls will be recorded.
     *
     * @method mockFailure
     * @param response_text The response text to fake.  It will be available
     *     as request.responseText in the request passed to the failure
     *     handler.
     * @param module The module to be instrumented.
     * @param status_code Optional HTTP status code.  This defaults to
     *     undefined, since the attribute may not always be available.
     */
    mockFailure: function(response_text, module, status_code) {
        var log = [];
        var mockXhr = new Y.Base();
        mockXhr.send = function(url, cfg) {
            log.push([url, cfg]);
            var response = make_fake_response(response_text, status_code);
            var arbitrary_txn_id = '4';
            cfg.on.failure(arbitrary_txn_id, response);
        };
        this.mockIO(mockXhr, module);
        return log;
    }

});

}, '0.1', {'requires': ['test', 'base']}
);
