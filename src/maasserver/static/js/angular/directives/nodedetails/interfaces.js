angular.module('MAAS').directive('nodeInterfaces', function() {
    const path = 'static/partials/nodedetails/interfaces.html';
    return {
        restrict: 'E',
        templateUrl: `${path}?v=${MAAS_config.files_version}`
    };
});
