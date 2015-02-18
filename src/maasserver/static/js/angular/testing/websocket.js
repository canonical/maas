/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Mock WebSocket
 *
 * Provides a mock websocket connection.
 */

var READY_STATES = {
    CONNECTING: 0,
    OPEN: 1,
    CLOSING: 2,
    CLOSED: 3
};

var MSG_TYPE = {
    REQUEST: 0,
    RESPONSE: 1
};

function MockWebSocket(url) {
    this.readyState = READY_STATES.CONNECTING;
    this.url = url;
    this.onclose = null;
    this.onerror = null;
    this.onmessage = null;
    this.onopen = null;

    this.sentData = [];
    this.returnData = [];
    this.receivedData = [];

    // Simulate the connection opening.
    var self = this;
    setTimeout(function() {
        self.readyState = READY_STATES.OPEN;
        if(angular.isFunction(self.onopen)) {
            self.onopen();
        }
    });
}

MockWebSocket.prototype.close = function() {
    this.readyState = READY_STATES.CLOSING;

    // Simulate the connection closing.
    var self = this;
    setTimeout(function() {
        self.readyState = READY_STATES.CLOSED;
        if(angular.isFunction(self.onclose)) {
            self.onclose();
        }
    });
};

MockWebSocket.prototype.send = function(data) {
    this.sentData.push(data);

    // Exit early if no fake data to return.
    if(this.returnData.length === 0) {
        return;
    }

    // Possible that the amount of data to recieve for this
    // send message is only one packet.
    var receivedData = this.returnData.shift();
    if(!angular.isArray(receivedData)) {
        receivedData = [receivedData];
    }

    var self = this;

    // Send the response
    setTimeout(function() {
        var sentObject = angular.fromJson(data);
        var sentType = sentObject.type;
        var sentId = sentObject.request_id;
        if(angular.isNumber(sentType) && angular.isNumber(sentId)) {
            // Patch the request_id so the response is the
            // same as the request.
            angular.forEach(receivedData, function(rData) {
                var rObject = angular.fromJson(rData);
                var rType = rObject.type;
                // Patch the request_id if the send message was a request and
                // the return message is a response. This allows the response
                // message in the queue to not know the request_id.
                if(angular.isNumber(rType) &&
                        sentType === MSG_TYPE.REQUEST &&
                        rType === MSG_TYPE.RESPONSE) {
                    rObject.request_id = sentId;
                }
                rData = angular.toJson(rObject);
                self.receivedData.push(rData);
                if(angular.isFunction(self.onmessage)) {
                    self.onmessage({ data: rData });
                }
            });
        } else {
            // Nothing to patch just send the response.
            angular.forEach(receivedData, function(rData) {
                self.receivedData.push(rData);
                if(angular.isFunction(self.onmessage)) {
                    self.onmessage({ data: rData });
                }
            });
        }
    });
};
