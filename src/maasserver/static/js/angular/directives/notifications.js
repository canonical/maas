/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Notifications.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject notifications.html into the template cache.
    $templateCache.put('directive/templates/notifications.html', [
      '<div ng-repeat="n in notifications" ng-class="classes[n.category]">',
        '<p class="p-notification__response">',
          '<span class="p-notification__status"></span>',
          '<span ng-bind-html="n.message"></span> — ',
          '<a ng-click="dismiss(n)">Dismiss</a>',
          '<br><small>(id: {$ n.id $}, ',
          'ident: {$ n.ident || "-" $}, user: {$ n.user || "-" $}, ',
          'users: {$ n.users $}, admins: {$ n.admins $}, ',
          'created: {$ n.created $}, updated: {$ n.updated $})</small>',
        '</p>',
      '</div>'
    ].join(''));
}]);

angular.module('MAAS').directive('maasNotifications', [
    "NotificationsManager", "ManagerHelperService",
    function(NotificationsManager, ManagerHelperService) {
        return {
            restrict: "E",
            templateUrl: 'directive/templates/notifications.html',
            link: function($scope, element, attrs) {
                ManagerHelperService.loadManager($scope, NotificationsManager);
                $scope.notifications = NotificationsManager.getItems();
                $scope.dismiss = angular.bind(
                    NotificationsManager, NotificationsManager.dismiss);
                $scope.classes = {
                    "error": "p-notification--error",
                    "warning": "p-notification--warning",
                    "success": "p-notification--success",
                    "info": "p-notification"  // No suffix.
                };
            }
        };
    }]);
