/* 'thin' directive, ~50% more performant than ng-include */
angular.module('MAAS').directive('storageDisksPartitions', function() {
    const path = 'static/partials/nodedetails/storage/disks-partitions.html';
    return {
        restrict: 'E',
        templateUrl: `${path}?v=${MAAS_config.files_version}`
    };
});
