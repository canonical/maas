angular.module('MAAS').directive('nodeSummary', function() {
    const path = 'static/partials/nodedetails/summary.html';
    return {
        restrict: 'E',
        templateUrl: `${path}?v=${MAAS_config.files_version}`
    };
});
