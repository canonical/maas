angular.module('MAAS').directive('nodeVlans', function() {
    const path = 'static/partials/nodedetails/vlans.html';
    return {
        restrict: 'E',
        templateUrl: `${path}?v=${MAAS_config.files_version}`
    };
});
