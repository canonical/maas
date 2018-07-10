angular.module('MAAS').directive('nodeConfiguration', function() {
    const path = 'static/partials/nodedetails/configuration.html';
    return {
        restrict: 'E',
        templateUrl: `${path}?v=${MAAS_config.files_version}`
    };
});
