/* Copyright 2014 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * The shortpoll module provides the functionality to deal with updating
 * in-browser data by polling the server.
 *
 * @module shortpoll
 */
YUI.add('maas.shortpoll', function(Y) {

var namespace = Y.namespace('maas.shortpoll');

// Event fired when the short-polling request starts.
namespace.shortpoll_start_event = 'maas.shortpoll.start';

// Event fired each time the short-polling request fails (to connect or
// to parse the returned result).
namespace.shortpoll_fail_event = 'maas.shortpoll.failure';

// After MAX_SHORT_DELAY_FAILED_ATTEMPTS failed connections (real failed
// connections or connection getting an invalid return) separated
// by SHORT_DELAY (millisec), wait LONG_DELAY (millisec) between
// each failed connection.
namespace.MAX_SHORT_DELAY_FAILED_ATTEMPTS = 5;
namespace.SHORT_DELAY = 15 * 1000;  // 15 seconds.
namespace.LONG_DELAY = 3 * 60 * 1000;  // 3 minutes.

// Ugly hack for tests, to prevent repolling.
namespace._repoll = true;

// Overridden by tests.
namespace._io = new Y.IO();

/**
 *
 * A ShortPollManager creates and manages a polling connection to the server
 * to fetch objects.
 *
 * @class ShortPollManager
 */
function ShortPollManager(config) {
    ShortPollManager.superclass.constructor.apply(this, arguments);
}

ShortPollManager.NAME = "shortPollManager";

ShortPollManager.ATTRS = {
    /**
     * The URI to poll.
     *
     * @attribute uri
     * @type string
     */
    uri: {
        value: ""
    },

    /**
     * The key with which to publish polled responses.
     *
     * @attribute eventKey
     * @type string
     */
    eventKey: {
        valueFn: function() {
            return Y.guid("shortpoll_");
        }
    },

    /**
     * The IO instance used.
     *
     * @attribute io
     * @type Y.IO
     */
    io: {
        readOnly: true,
        getter: function() {
            return namespace._io;
        }
    }
};

Y.extend(ShortPollManager, Y.Base, {
    initializer : function(cfg) {
        this._started = false;
        this._failed_attempts = 0;
        this._sequence = 0;
    },

    successPoll : function (id, response) {
        try {
            var eventKey = this.get("eventKey");
            var data = Y.JSON.parse(response.responseText);
            Y.fire(eventKey, data);
            return true;
        }
        catch (e) {
            Y.fire(namespace.shortpoll_fail_event, e);
            return false;
        }
    },

    failurePoll : function () {
        Y.fire(namespace.shortpoll_fail_event);
    },

    /**
     * Return the delay (milliseconds) to wait before trying to reconnect
     * again after a failed connection.
     *
     * The rationale here is that:
     * 1. We should not try to reconnect instantaneously after a failed
     *    connection.
     * 2. After a certain number of failed connections, we should set the
     *    delay between two failed connection to a bigger number because the
     *    server may be having problems.
     *
     * @method _pollDelay
     */
    _pollDelay : function() {
        if (this._failed_attempts >=
                namespace.MAX_SHORT_DELAY_FAILED_ATTEMPTS) {
            return namespace.LONG_DELAY;
        }
        else {
            return namespace.SHORT_DELAY;
        }
    },

    /**
     * Relaunch a connection to the server after a successful or
     * a failed connection.
     *
     * @method repoll
     * @param {Boolean} failed: whether or not the previous connection
     *     has failed.
     */
    repoll : function(failed) {
        if (failed) {
            this._failed_attempts += 1;
        }
        else {
            this._failed_attempts = 0;
        }
        if (namespace._repoll) {
            var delay = this._pollDelay();
            Y.later(delay, this, this.poll);
            return delay;
        }
        else {
            return this._pollDelay();
        }
    },

    poll : function() {
        var that = this;
        var config = {
            method: "GET",
            sync: false,
            on: {
                failure: function(id, response) {
                    if (Y.Lang.isValue(response) &&
                        Y.Lang.isValue(response.status) &&
                        (response.status === 408 ||
                         response.status === 504)) {
                        // If the error code is:
                        // - 408 Request timeout
                        // - 504 Gateway timeout
                        // Then ignore the error and start
                        // polling again.
                        that.repoll(false);
                    }
                    else {
                        that.failurePoll();
                        that.repoll(true);
                    }
                },
                success: function(id, response) {
                    var success = that.successPoll(id, response);
                    that.repoll(!success);
                }
            }
        };
        this._sequence = this._sequence + 1;
        var poll_uri = this.get("uri");
        if (poll_uri.indexOf("?") >= 0) {
            poll_uri += "&sequence=" + this._sequence;
        }
        else {
            poll_uri += "?sequence=" + this._sequence;
        }
        if (!this._started) {
            Y.fire(namespace.shortpoll_start_event);
            this._started = true;
        }
        this.get("io").send(poll_uri, config);
    }
});

namespace.ShortPollManager = ShortPollManager;

}, "0.1", {"requires":["base", "event", "json", "io"]});
