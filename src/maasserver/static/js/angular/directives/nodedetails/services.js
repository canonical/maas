angular.module('MAAS').directive('nodeServices', function() {
    const path = 'static/partials/nodedetails/services.html';
    return {
        restrict: 'E',
        templateUrl: `${path}?v=${MAAS_config.files_version}`
    };
});
