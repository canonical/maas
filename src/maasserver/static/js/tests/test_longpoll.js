/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.longpoll.tests', function(Y) {

Y.log('loading maas.longpoll.tests');
var namespace = Y.namespace('maas.longpoll.tests');

var longpoll = Y.maas.longpoll;
var suite = new Y.Test.Suite("maas.longpoll Tests");

suite.add(new Y.maas.testing.TestCase({
    name: 'test-longpoll-singleton',

    tearDown: function() {
        // Cleanup the singleton;
        longpoll._manager = null;
    },

    testGetSingletonLongPollManager: function() {
        Y.Assert.isNull(longpoll._manager);
        var manager = longpoll.getLongPollManager();
        Y.Assert.isNotNull(longpoll._manager);
        var manager2 = longpoll.getLongPollManager();
        Y.Assert.areSame(manager, manager2);
    }

}));

suite.add(new Y.maas.testing.TestCase({
    name: 'test-longpoll',

    setUp: function() {
        var old_repoll = longpoll._repoll;
        longpoll._repoll = false;
        this.addCleanup(function() {longpoll._repoll = old_repoll});
    },

    tearDown: function() {
        // Cleanup the singleton.
        longpoll._manager = null;
    },

    testInitLongPollManagerQueueName: function() {
        var manager = longpoll.setupLongPollManager('key', '/longpoll/');
        Y.Assert.areEqual('key', manager.key);
        Y.Assert.areEqual('/longpoll/', manager.uri);
        Y.Assert.isFalse(Y.Lang.isValue(manager.nb_calls));
    },

    testPollStarted: function() {
        var fired = false;
        Y.on(longpoll.longpoll_start_event, function() {
            fired = true;
        });
        var manager = longpoll.setupLongPollManager('key', '/longpoll/');
        Y.Assert.isTrue(fired, "Start event not fired.");
    },

    testPollFailure: function() {
        var fired = false;
        Y.on(longpoll.longpoll_fail_event, function() {
            fired = true;
        });
        // Monkeypatch io to simulate failure.
        var manager = longpoll.getLongPollManager();
        var mockXhr = new Y.Base();
        mockXhr.send = function(uri, cfg) {
            cfg.on.failure();
        };
        this.mockIO(mockXhr, longpoll);
        var manager = longpoll.setupLongPollManager('key', '/longpoll/');
        Y.Assert.isTrue(fired, "Failure event not fired.");
    },

    testSuccessPollInvalidData: function() {
        var manager = longpoll.getLongPollManager();
        var custom_response = "{{";
        var response = {
            responseText: custom_response
        };
        var res = manager.successPoll("2", response);
        Y.Assert.isFalse(res);
    },

    testSuccessPollMalformedData: function() {
        var manager = longpoll.getLongPollManager();
        var response = {
            responseText: '{ "something": "6" }'
        };
        var res = manager.successPoll("2", response);
        Y.Assert.isFalse(res);
     },

     testSuccessPollWellformedData: function() {
        var manager = longpoll.getLongPollManager();
        var response = {
            responseText: '{ "event_key": "4", "something": "6"}'
        };
        var res = manager.successPoll("2", response);
        Y.Assert.isTrue(res);
    },

    testPollDelay: function() {
        // Create event listeners.
        var longdelay_event_fired = false;
        Y.on(longpoll.longpoll_longdelay, function(data) {
            longdelay_event_fired = true;
        });
        var shortdelay_event_fired = false;
        Y.on(longpoll.longpoll_shortdelay, function(data) {
            shortdelay_event_fired = true;
        });
        var manager = longpoll.getLongPollManager();
        // Monkeypatch io to simulate failure.
        var mockXhr = new Y.Base();
        mockXhr.send = function(uri, cfg) {
            cfg.on.failure();
        };
        this.mockIO(mockXhr, longpoll);
        Y.Assert.areEqual(0, manager._failed_attempts);
        var manager = longpoll.setupLongPollManager('key', '/longpoll/');
        Y.Assert.areEqual(1, manager._failed_attempts);
        var i, delay;
        for (i=0; i<longpoll.MAX_SHORT_DELAY_FAILED_ATTEMPTS-2; i++) {
            Y.Assert.areEqual(i+1, manager._failed_attempts);
            delay = manager._pollDelay();
            Y.Assert.areEqual(delay, longpoll.SHORT_DELAY);
        }
        // After MAX_SHORT_DELAY_FAILED_ATTEMPTS failed attempts, the
        // delay returned by _pollDelay is LONG_DELAY and
        // longpoll_longdelay is fired.
        Y.Assert.isFalse(longdelay_event_fired);
        delay = manager._pollDelay();
        Y.Assert.isTrue(longdelay_event_fired);
        Y.Assert.areEqual(delay, longpoll.LONG_DELAY);

        // Monkeypatch io to simulate success.
        var mockXhr = new Y.Base();
        mockXhr.send = function(uri, cfg) {
            var out = {};
            out.responseText = Y.JSON.stringify({'event_key': 'response'});
            cfg.on.success(4, out);
        };
        this.mockIO(mockXhr, longpoll);
        // After a success, longpoll.longpoll_shortdelay is fired.
        Y.Assert.isFalse(shortdelay_event_fired);
        delay = manager.poll();
        Y.Assert.isTrue(shortdelay_event_fired);
    },

    testPollUriSequence: function() {
        // Each new polling increases the sequence parameter:
        // /longpoll/?uuid=key&sequence=1
        // /longpoll/?uuid=key&sequence=2
        // /longpoll/?uuid=key&sequence=3
        // ...
        var count = 0;
        // Monkeypatch io to simulate failure.
        var manager = longpoll.getLongPollManager();
        var mockXhr = new Y.Base();
        mockXhr.send = function(uri, cfg) {
            Y.Assert.areEqual(
                '/longpoll/?uuid=key&sequence=' + (count+1),
                uri);
            count = count + 1;
            var response = {
               responseText: '{"i":2}'
            };
            cfg.on.success(2, response);
        };
        this.mockIO(mockXhr, longpoll);
        longpoll.setupLongPollManager('key', '/longpoll/');
        var request;
        for (request=1; request<10; request++) {
            Y.Assert.isTrue(count === request, "Uri not requested.");
            manager.poll();
        }
    },

    _testDoesNotFail: function(error_code) {
        // Assert that, when the longpoll request receives an error
        // with code error_code, it is not treated as a failed
        // connection attempt.
        var manager = longpoll.getLongPollManager();
        // Monkeypatch io to simulate a request timeout.
        var mockXhr = new Y.Base();
        mockXhr.send = function(uri, cfg) {
            response = {status: error_code};
            cfg.on.failure(4, response);
        };
        this.mockIO(mockXhr, longpoll);

        Y.Assert.areEqual(0, manager._failed_attempts);
        longpoll.setupLongPollManager('key', '/longpoll/');
        Y.Assert.areEqual(0, manager._failed_attempts);
    },

    test408RequestTimeoutHandling: function() {
        this._testDoesNotFail(408);
    },

    test504GatewayTimeoutHandling: function() {
        this._testDoesNotFail(504);
    },

    testPollPayLoadBad: function() {
        // If a non valid response is returned, longpoll_fail_event
        // is fired.
        var fired = false;
        Y.on(longpoll.longpoll_fail_event, function() {
            fired = true;
        });
        var manager = longpoll.getLongPollManager();
        var response = "{non valid json";
        this.mockSuccess(response, longpoll);
        longpoll.setupLongPollManager('key', '/longpoll/');
        Y.Assert.isTrue(fired, "Failure event not fired.");
    },

    testPollPayLoadOk: function() {
        // Create a valid message.
        var custom_response = {
            'event_key': 'my-event',
            'something': {something_else: 1234}
        };
        var fired = false;
        Y.on(custom_response.event_key, function(data) {
            fired = true;
            Y.Assert.areEqual(data, custom_response);
        });
        var manager = longpoll.getLongPollManager();
        // Monkeypatch io.
        var mockXhr = new Y.Base();
        mockXhr.send = function(uri, cfg) {
            var out = {};
            out.responseText = Y.JSON.stringify(custom_response);
            cfg.on.success(4, out);
        };
        this.mockIO(mockXhr, longpoll);
        longpoll.setupLongPollManager('key', '/longpoll/');
        Y.Assert.isTrue(fired, "Custom event not fired.");
    }

}));


namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.longpoll']}
);
