angular.module('MAAS').directive('nodeStorage', function() {
    const path = 'static/partials/nodedetails/storage.html';
    return {
        restrict: 'E',
        templateUrl: `${path}?v=${MAAS_config.files_version}`
    };
});
