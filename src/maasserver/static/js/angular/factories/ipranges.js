/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS IPRange Manager
 *
 * Manages all of the IPRanges in the browser. The manager uses the
 * RegionConnection to load the IPRanges, update the IPRanges, and listen for
 * notification events about IPRanges.
 */

function IPRangesManager(RegionConnection, Manager) {
  function IPRangesManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "iprange";

    // Listen for notify events for the iprange object.
    var self = this;
    RegionConnection.registerNotifier("iprange", function(action, data) {
      self.onNotify(action, data);
    });
  }

  IPRangesManager.prototype = new Manager();

  return new IPRangesManager();
}

IPRangesManager.$inject = ["RegionConnection", "Manager"];

export default IPRangesManager;
