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

// Message types (copied from region.js)
const MSG_TYPE = {
  REQUEST: 0,
  RESPONSE: 1,
  NOTIFY: 2,
  PING: 3,
  PING_REPLY: 4
};

function MockWebSocket(url) {
  this.readyState = READY_STATES.CONNECTING;
  this.url = url;
  this.onclose = null;
  this.onerror = null;
  this.onmessage = null;
  this.onopen = null;

  this.replyToPing = true;

  this.sentData = [];
  this.returnData = [];
  this.receivedData = [];

  this.sequenceNum = 0;

  // Simulate the connection opening.
  let self = this;
  setTimeout(function() {
    self.readyState = READY_STATES.OPEN;
    if (angular.isFunction(self.onopen)) {
      self.onopen();
    }
  });
}

MockWebSocket.prototype.close = function() {
  this.readyState = READY_STATES.CLOSING;

  // Simulate the connection closing.
  let self = this;
  setTimeout(function() {
    self.readyState = READY_STATES.CLOSED;
    if (angular.isFunction(self.onclose)) {
      self.onclose();
    }
  });
};

MockWebSocket.prototype.send = function(data) {
  let sentObject = angular.fromJson(data);
  let sentType = sentObject.type;
  let sentId = sentObject.request_id;
  let self = this;

  // Special case for PING type; just reply and return.
  if (
    self.replyToPing &&
    angular.isNumber(sentType) &&
    sentType === MSG_TYPE.PING
  ) {
    setTimeout(function() {
      self.sequenceNum += 1;
      let pingResultData = angular.toJson({
        type: MSG_TYPE.PING_REPLY,
        request_id: sentId,
        result: self.sequenceNum
      });
      self.onmessage({ data: pingResultData });
    });
    return;
  }

  this.sentData.push(data);

  // Exit early if no fake data to return.
  if (this.returnData.length === 0) {
    return;
  }

  // Possible that the amount of data to recieve for this
  // send message is only one packet.
  var receivedData = this.returnData.shift();
  if (!angular.isArray(receivedData)) {
    receivedData = [receivedData];
  }

  // Send the response
  setTimeout(function() {
    if (angular.isNumber(sentType) && angular.isNumber(sentId)) {
      // Patch the request_id so the response is the
      // same as the request.
      angular.forEach(receivedData, function(rData) {
        var rObject = angular.fromJson(rData);
        var rType = rObject.type;
        // Patch the request_id if the send message was a request and
        // the return message is a response. This allows the response
        // message in the queue to not know the request_id.
        if (
          angular.isNumber(rType) &&
          sentType === MSG_TYPE.REQUEST &&
          rType === MSG_TYPE.RESPONSE
        ) {
          rObject.request_id = sentId;
        }
        rData = angular.toJson(rObject);
        self.receivedData.push(rData);
        if (angular.isFunction(self.onmessage)) {
          self.onmessage({ data: rData });
        }
      });
    } else {
      // Nothing to patch just send the response.
      angular.forEach(receivedData, function(rData) {
        self.receivedData.push(rData);
        if (angular.isFunction(self.onmessage)) {
          self.onmessage({ data: rData });
        }
      });
    }
  });
};

export default MockWebSocket;
