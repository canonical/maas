/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * The Longpoll module provides the functionnality to deal with longpolling
 * on the JavaScript side.
 *
 * The module method setupLongPollManager is the one that should be
 * called to start the longpolling.
 *
 * Then you will probably want to create Javascript handlers for the events
 * which will be fired:
 *    - event_key will be fired when the event on the server side is triggered
 *    (event_key being the name of the event on the server side).
 *    - see below for other events fired by the longpoll machinery.
 *
 * @module longpoll
 */
YUI.add('maas.longpoll', function(Y) {

var namespace = Y.namespace('maas.longpoll');

// Event fired when the long polling request starts.
namespace.longpoll_start_event = 'maas.longpoll.start';

// Event fired each time the long polling request fails (to connect or
// to parse the returned result).
namespace.longpoll_fail_event = 'maas.longpoll.failure';

// Event fired when the delay between each failed connection is set to
// a long delay (after MAX_SHORT_DELAY_FAILED_ATTEMPTS failed attempts).
namespace.longpoll_longdelay = 'maas.longpoll.longdelay';

// Event fired when the delay between each failed connection is set back
// to a short delay.
namespace.longpoll_shortdelay = 'maas.longpoll.shortdelay';

namespace._manager = null;

// After MAX_SHORT_DELAY_FAILED_ATTEMPTS failed connections (real failed
// connections or connection getting an invalid return) separated
// by SHORT_DELAY (millisec), wait LONG_DELAY (millisec) between
// each failed connection.
namespace.MAX_SHORT_DELAY_FAILED_ATTEMPTS = 5;
namespace.SHORT_DELAY = 1000;
namespace.LONG_DELAY = 3*60*1000;

/**
 *
 * A Long Poll Manager creates and manages a long polling connexion
 * to the server to fetch events. This class is not directly used
 * but managed through 'setupLongPollManager' which creates and
 * initialises a singleton LongPollManager.
 *
 * @class LongPollManager
 */
function LongPollManager(config) {
    LongPollManager.superclass.constructor.apply(this, arguments);
}

LongPollManager.NAME = "longPollManager";

namespace._repoll = true;

namespace._io = new Y.IO();

Y.extend(LongPollManager, Y.Base, {
    initializer : function(cfg) {
        this._started = false;
        this._failed_attempts = 0;
        this._sequence = 0;
    },

    setConnectionInfos : function(key, uri) {
        this.key = key;
        this.uri = uri;
    },

    successPoll : function (id, response) {
        try {
            var data = Y.JSON.parse(response.responseText);
            Y.fire(data.event_key, data);
            return true;
        }
        catch (e) {
            Y.fire(namespace.longpoll_fail_event, e);
            return false;
        }
    },

    failurePoll : function () {
        Y.fire(namespace.longpoll_fail_event);
    },

    /**
     * Return the delay (milliseconds) to wait before trying to reconnect
     * again after a failed connection.
     *
     * The rationale here is that:
     * 1. We should not try to reconnect instantaneously after a failed
     *     connection.
     * 2. After a certain number of failed connections, we should set the
     *     delay between two failed connection to a bigger number because
     *     the server may be having problems.
     *
     * @method _pollDelay
     */
    _pollDelay : function() {
        this._failed_attempts = this._failed_attempts + 1;
        if (this._failed_attempts >=
                namespace.MAX_SHORT_DELAY_FAILED_ATTEMPTS) {
            Y.fire(namespace.longpoll_longdelay);
            Y.log('Switching into long delay mode.');
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
        if (!failed) {
            if (this._failed_attempts >=
                    namespace.MAX_SHORT_DELAY_FAILED_ATTEMPTS) {
                Y.fire(namespace.longpoll_shortdelay);
            }
            this._failed_attempts = 0;
            if (namespace._repoll) {
                this.poll();
            }
        }
        else {
            var delay = this._pollDelay();
            if (namespace._repoll) {
                Y.later(delay, this, this.poll);
            }
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
        var queue_uri = this.uri +
            "?uuid=" + this.key +
            "&sequence=" + this._sequence;
        if (!this._started) {
            Y.fire(namespace.longpoll_start_event);
            this._started = true;
        }
        namespace._io.send(queue_uri, config);
    }
});

namespace.LongPollManager = LongPollManager;

namespace.getLongPollManager = function() {
    if (!Y.Lang.isValue(namespace._manager)) {
        namespace._manager = new namespace.LongPollManager();
    }
    return namespace._manager;
};

namespace.setupLongPollManager = function(key, uri) {
    var longpollmanager = namespace.getLongPollManager();
    longpollmanager.setConnectionInfos(key, uri);
    longpollmanager.poll();
    return longpollmanager;
};

}, "0.1", {"requires":["base", "event", "json", "io"]});
