/* 'thin' directive, ~50% more performant than ng-include */
angular.module('MAAS').directive('storageFilesystems', function() {
    const path = 'static/partials/nodedetails/storage/filesystems.html';
    return {
        restrict: 'E',
        templateUrl: `${path}?v=${MAAS_config.files_version}`
    };
});
