/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Notifications.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject notifications.html into the template cache.
    $templateCache.put('directive/templates/notifications.html', [
      '<div ng-repeat="category in categories"',
        ' ng-init="notifications = categoryNotifications[category]">',
        // 1 notification.
        '<div ng-if="notifications.length == 1"',
        ' ng-class="categoryClasses[category]">',
          '<p ng-repeat="notification in notifications"',
          ' class="p-notification__response">',
            '<span ng-bind-html="notification.message"></span> ',
            '<button class="button--base button--inline"',
            ' ng-click="dismiss(notification)">Dismiss</button>',
          '</p>',
        '</div>',
        // 2 or more notifications.
        '<div ng-if="notifications.length >= 2"',
        ' ng-class="categoryClasses[category]"',
        ' ng-init="shown = false"',
        ' class="p-notification--group">',
          '<p class="p-notification__response" tabindex="0"',
            ' aria-label="{$ notifications.length $} ',
            '{$ categoryTitles[category] $}, click to open messages."',
            ' maas-enter="shown = !shown"',
            ' ng-click="shown = !shown">',
            '<span class="p-notification__status"',
            ' data-count="{$ notifications.length $}"',
            ' ng-bind="categoryTitles[category]"></span>',
            '<i class="icon icon--open"></i>',
          '</p>',
          '<ul class="p-notification__list" ng-class="{\'is-open\': shown}">',
            '<li ng-repeat="notification in notifications"',
            ' class="p-notification__item">',
              '<p class="p-notification__msg">',
                '<span ng-bind-html="notification.message"></span> ',
                '<button class="button--base button--inline"',
                ' ng-click="dismiss(notification)">Dismiss</button>',
              '</p>',
              '<time class="p-notification__date" ',
              ' ng-bind="notification.updated"></time>',
            '</li>',
          '</ul>',
        '</div>',
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

                $scope.categories = [
                    "error",
                    "warning",
                    "success",
                    "info"
                ];
                $scope.categoryTitles = {
                    error: "Errors",
                    warning: "Warnings",
                    success: "Successes",
                    info: "Other messages"
                };
                $scope.categoryClasses = {
                    error: "p-notification--error",
                    warning: "p-notification--warning",
                    success: "p-notification--success",
                    info: "p-notification"  // No suffix.
                };
                $scope.categoryNotifications = {
                    error: [],
                    warning: [],
                    success: [],
                    info: []
                };

                $scope.$watchCollection(
                    "notifications", function() {
                        var cns = $scope.categoryNotifications;
                        angular.forEach(
                            $scope.categories, function(category) {
                                cns[category].length = 0;
                            }
                        );
                        angular.forEach(
                            $scope.notifications, function(notification) {
                                cns[notification.category].push(notification);
                            }
                        );
                    }
                );
            }
        };
    }]);
