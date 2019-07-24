/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Notifications.
 */

/* @ngInject */
export function cacheNotifications($templateCache) {
  // Inject notifications.html into the template cache.
  $templateCache.put(
    "directive/templates/notifications.html",
    [
      '<div class="" data-ng-repeat="category in categories"',
      ' data-ng-init="notifications = categoryNotifications[category]">',
      // 1 notification.
      '<span class="row" data-ng-if="notifications.length == 1">',
      '<ul class="p-list" data-ng-class="{\'is-open\': shown}">',
      '<li data-ng-repeat="notification in notifications"',
      ' class="p-notification"',
      ' data-ng-class="categoryClasses[notification.category]">',
      '<p class="p-notification__response">',
      '<span data-ng-bind-html="notification.message"></span> ',
      '<a class="p-notification__action"',
      ' data-ng-click="dismiss(notification)">Dismiss</a>',
      "</p>",
      "</li>",
      "</ul>",
      "</span>",
      // 2 or more notifications.
      '<div class="row p-notification--group" ',
      'data-ng-if="notifications.length >= 2"',
      ' data-ng-init="shown = false">',
      '<div data-ng-class="categoryClasses[notifications[0].category]">',
      '<a aria-label="{$ notifications.length $} ',
      '{$ categoryTitles[category] $}, click to open messages."',
      ' maas-enter="shown = !shown"',
      ' class="p-notification__toggle"',
      ' data-ng-click="shown = !shown">',
      '<p class="p-notification__response">',
      '<span class="p-notification__status"',
      ' data-count="{$ notifications.length $}"',
      " data-ng-bind=\"notifications.length + ' ' + ",
      'categoryTitles[category]"></span>',
      "<small>",
      "<i data-ng-class=\"{ 'p-icon--expand': !shown,",
      " 'p-icon--collapse': shown }\"></i></small>",
      "</p>",
      "</a>",
      '<ul class="p-list--divided u-no-margin--bottom" ',
      "data-ng-class=\"{'u-hide': !shown}\">",
      '<li data-ng-repeat="notification in notifications"',
      ' class="p-list__item">',
      '<p class="p-notification__response">',
      '<span data-ng-bind-html="notification.message">',
      "</span> ",
      '<a class="p-notification__action"',
      ' data-ng-click="dismiss(notification)">Dismiss</a>',
      "</p>",
      "</li>",
      "</ul>",
      "</div>",
      "</div>",
      "</div>"
    ].join("")
  );
}

/* @ngInject */
export function maasNotifications(NotificationsManager, ManagerHelperService) {
  return {
    restrict: "E",
    templateUrl: "directive/templates/notifications.html",
    link: function(scope, element, attrs) {
      ManagerHelperService.loadManager(scope, NotificationsManager);
      scope.notifications = NotificationsManager.getItems();
      scope.dismiss = angular.bind(
        NotificationsManager,
        NotificationsManager.dismiss
      );

      scope.categories = ["error", "warning", "success", "info"];
      scope.categoryTitles = {
        error: "Errors",
        warning: "Warnings",
        success: "Successes",
        info: "Other messages"
      };
      scope.categoryClasses = {
        error: "p-notification--negative",
        warning: "p-notification--caution",
        success: "p-notification--positive",
        info: "p-notification" // No suffix.
      };
      scope.categoryNotifications = {
        error: [],
        warning: [],
        success: [],
        info: []
      };

      scope.$watchCollection("notifications", function() {
        var cns = scope.categoryNotifications;
        angular.forEach(scope.categories, function(category) {
          cns[category].length = 0;
        });
        angular.forEach(scope.notifications, function(notification) {
          cns[notification.category].push(notification);
        });
      });
    }
  };
}
