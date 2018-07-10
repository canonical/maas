angular.module('MAAS').directive('nodeEvents', function() {
    const path = 'static/partials/nodedetails/events.html';
    return {
        restrict: 'E',
        templateUrl: `${path}?v=${MAAS_config.files_version}`
    };
});
