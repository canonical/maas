angular.module('MAAS').directive('nodeLogs', function() {
    const path = 'static/partials/nodedetails/logs.html';
    return {
        restrict: 'E',
        templateUrl: `${path}?v=${MAAS_config.files_version}`
    };
});
