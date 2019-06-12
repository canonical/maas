/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Pods Manager
 *
 * Manages all of the pods in the browser. The manager uses the
 * RegionConnection to load the pods, update the pods, and listen for
 * notification events about pods.
 */

function PodsManager(RegionConnection, Manager, $location, $routeParams) {
  function PodsManager() {
    Manager.call(this);

    this._pk = "id";
    this._handler = "pod";

    // Listen for notify events for the pod object.
    var self = this;
    RegionConnection.registerNotifier("pod", function(action, data) {
      self.onNotify(action, data);
    });
  }

  PodsManager.prototype = new Manager();

  // Refresh the pod information
  PodsManager.prototype.refresh = function(pod) {
    var self = this;
    return RegionConnection.callMethod("pod.refresh", pod).then(function(pod) {
      self._replaceItem(pod);
      return pod;
    });
  };

  // Compose a machine in the pod.
  PodsManager.prototype.compose = function(params) {
    var self = this;
    return RegionConnection.callMethod("pod.compose", params).then(function(
      pod
    ) {
      self._replaceItem(pod);
      return pod;
    });
  };

  // Calculate the available cores with overcommit applied
  PodsManager.prototype.availableWithOvercommit = function(
    total,
    used,
    overcommitRatio,
    precisionValue
  ) {
    if (precisionValue) {
      return (total * overcommitRatio - used)
        .toFixed(precisionValue)
        .replace(/[.,]0$/, "");
    } else {
      return total * overcommitRatio - used;
    }
  };

  // Detect if on RSD page
  PodsManager.prototype.onRSDSection = function(podID) {
    return $location.path() === "/rsd" || $location.path() === "/rsd/" + podID;
  };

  return new PodsManager();
}

PodsManager.$inject = [
  "RegionConnection",
  "Manager",
  "$location",
  "$routeParams"
];

export default PodsManager;
