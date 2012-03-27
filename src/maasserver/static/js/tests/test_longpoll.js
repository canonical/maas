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
        this.addCleanup(function() {longpoll._repoll = old_repoll; });
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
        var manager = longpoll.getLongPollManager();
        // Simulate failure.
        this.mockFailure('unused', longpoll);
        longpoll.setupLongPollManager('key', '/longpoll/');
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
        // Simulate failure.
        this.mockFailure('unused', longpoll);
        Y.Assert.areEqual(0, manager._failed_attempts);
        longpoll.setupLongPollManager('key', '/longpoll/');
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

        // Simulate success.
        this.mockSuccess(
            Y.JSON.stringify({'event_key': 'response'}), longpoll);

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
        var manager = longpoll.getLongPollManager();
        // Simulate success.
        var log = this.mockSuccess('{"i":2}', longpoll);
        longpoll.setupLongPollManager('key', '/longpoll/');
        var request;
        for (request=1; request<10; request++) {
            manager.poll();
            Y.Assert.areEqual(
                '/longpoll/?uuid=key&sequence=' + (request + 1),
                log.pop()[0]);
        }
    },

    _testDoesNotFail: function(error_code) {
        // Assert that, when the longpoll request receives an error
        // with code error_code, it is not treated as a failed
        // connection attempt.
        var manager = longpoll.getLongPollManager();
        // Simulate a request timeout.
        this.mockFailure('{"i":2}', longpoll, error_code);

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
        var event_payload = null;
        Y.on(custom_response.event_key, function(data) {
            event_payload = data;
        });
        var manager = longpoll.getLongPollManager();
        // Simulate success.
        this.mockSuccess(Y.JSON.stringify(custom_response), longpoll);
        longpoll.setupLongPollManager('key', '/longpoll/');
        // Note that a utility to compare objects does not yet exist in YUI.
        // http://yuilibrary.com/projects/yui3/ticket/2529868.
        Y.Assert.areEqual('my-event', event_payload.event_key);
        Y.Assert.areEqual(
            1234, event_payload.something.something_else);
    }

}));


namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.longpoll']}
);
