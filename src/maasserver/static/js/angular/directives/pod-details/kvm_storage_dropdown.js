/* Copyright 2017-2018 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Directive for KVM storage dropdown.
 *
 */

/* @ngInject */
function kvmStorageDropdown($document) {
  return {
    restrict: "E",
    scope: {
      compose: "<",
      pod: "<",
      storage: "<",
      updateRequests: "<"
    },
    templateUrl: "static/partials/pod-details/kvm-storage-dropdown.html",
    link: (scope, element) => {
      scope.clickHandler = event => {
        const closestRow = element.closest("tr");
        const clickedInsideRow = closestRow.find(event.target).length > 0;

        if (clickedInsideRow) {
          return;
        }
        scope.$apply(scope.closeDropdown);
      };

      $document.on("click", scope.clickHandler);
      scope.$on("$destroy", () => $document.off("click", scope.clickHandler));
    },
    controller: KVMStorageDropdownController
  };
}

/* @ngInject */
function KVMStorageDropdownController($scope, $filter) {
  $scope.dropdownOpen = false;

  $scope.closeDropdown = () => {
    $scope.dropdownOpen = false;
  };

  $scope.toggleDropdown = () => {
    $scope.dropdownOpen = !$scope.dropdownOpen;
  };

  $scope.poolOverCapacity = storage => {
    const { compose, pod } = $scope;

    if (compose && compose.obj && pod && pod.storage_pools) {
      const storagePool = pod.storage_pools.find(
        pool => pool.id === storage.pool.id
      );
      const request = compose.obj.requests.find(
        req => storagePool.id === req.poolId
      );
      const requestSize = request ? request.size : 0;

      if (
        $filter("convertGigabyteToBytes")(requestSize) > storagePool.available
      ) {
        return true;
      }
    }
    return false;
  };

  $scope.totalStoragePercentage = (storage_pool, storage, other) => {
    const used = (storage_pool.used / storage_pool.total) * 100;
    const requested = (storage / storage_pool.total) * 100;
    const otherRequested = (other / storage_pool.total) * 100;
    let percent = used + requested;

    if (other) {
      percent = used + requested + otherRequested;
    }
    return percent;
  };

  $scope.getOtherRequests = (storagePool, storage) => {
    const request = $scope.compose.obj.requests.find(
      req => storagePool.id === req.poolId
    );
    let requestSize = request ? request.size : 0;

    if (storagePool.id === storage.pool.id) {
      requestSize -= storage.size;
    }

    return requestSize;
  };

  $scope.selectStoragePool = (storagePool, storage, isDisabled) => {
    if (!isDisabled) {
      storage.pool = storagePool;
      $scope.updateRequests();
    }
  };
}

export default kvmStorageDropdown;
