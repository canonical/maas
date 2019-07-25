/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS DHCPSnippet Manager
 *
 * Manages all of the DHCPSnippets in the browser. The manager uses the
 * RegionConnection to load the DHCPSnippets, update the DHCPSnippets, and
 * listen for notification events about DHCPSnippets.
 */

function DHCPSnippetsManager(RegionConnection, Manager) {
  function DHCPSnippetsManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "dhcpsnippet";

    // Listen for notify events for the DHCPSnippet object.
    var self = this;
    RegionConnection.registerNotifier("dhcpsnippet", function(action, data) {
      self.onNotify(action, data);
    });
  }

  DHCPSnippetsManager.prototype = new Manager();

  // Create the snippet.
  DHCPSnippetsManager.prototype.create = function(snippet) {
    return RegionConnection.callMethod(
      this._handler + ".create",
      snippet,
      true
    );
  };

  // Return filtered snippets applied to items
  DHCPSnippetsManager.prototype.getFilteredSnippets = (snippets, subnets) => {
    // should really pass in an array of subnet IPs
    // the subnet IP should be added to the snippet prior to
    // being passed into this method
    if (angular.isUndefined(subnets) || !angular.isArray(subnets)) {
      return [];
    }

    if (angular.isUndefined(snippets) || !angular.isArray(snippets)) {
      return [];
    }

    const filteredSubnets = snippets.filter(snippet => {
      return subnets.indexOf(snippet.subnet_cidr) !== -1;
    });

    return filteredSubnets;
  };

  return new DHCPSnippetsManager();
}

DHCPSnippetsManager.$inject = ["RegionConnection", "Manager"];

export default DHCPSnippetsManager;
