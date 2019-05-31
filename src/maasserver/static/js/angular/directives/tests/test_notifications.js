/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for notifications directive.
 */

import MockWebSocket from "testing/websocket";

describe("maasNotifications", function() {
  // Load the MAAS module.
  beforeEach(angular.mock.module("MAAS"));

  // Some example notifications as sent from the server.
  var exampleNotifications = [
    {
      id: 1,
      ident: null,
      message: "Attention admins!",
      category: "error",
      user: null,
      users: false,
      admins: true,
      created: "Fri, 27 Jan. 2017 12:19:52",
      updated: "Fri, 27 Jan. 2017 12:19:52"
    },
    {
      id: 2,
      ident: null,
      message: "Dear users, ...",
      category: "warning",
      user: null,
      users: true,
      admins: false,
      created: "Fri, 27 Jan. 2017 12:19:52",
      updated: "Fri, 27 Jan. 2017 12:19:52"
    },
    {
      id: 3,
      ident: null,
      message: "Greetings, Individual!",
      category: "info",
      user: 1,
      users: false,
      admins: false,
      created: "Fri, 27 Jan. 2017 12:19:52",
      updated: "Fri, 27 Jan. 2017 12:19:52"
    }
  ];
  var exampleAdditionalNotification = {
    id: 4,
    ident: null,
    message: "I'm only sleeping",
    category: "info",
    user: null,
    users: true,
    admins: true,
    created: "Thu, 16 Feb. 2017 16:39:36",
    updated: "Thu, 16 Feb. 2017 16:39:36"
  };

  // Load the NotificationsManager and
  // create a new scope before each test.
  var theNotificationsManager;
  var $scope;

  beforeEach(inject(function($rootScope, NotificationsManager, $injector) {
    theNotificationsManager = NotificationsManager;
    $scope = $rootScope.$new();
    // Mock buildSocket so an actual connection is not made.
    let RegionConnection = $injector.get("RegionConnection");
    let webSocket = new MockWebSocket();
    spyOn(RegionConnection, "buildSocket").and.returnValue(webSocket);
  }));

  describe("maas-notifications", function() {
    // Return the compiled directive.
    function compileDirective() {
      var directive;
      var html = "<maas-notifications></maas-notifications>";

      // Compile the directive.
      inject(function($compile) {
        directive = $compile(html)($scope);
      });

      // Perform the digest cycle to finish the compile.
      $scope.$digest();
      return directive;
    }

    it("renders notifications", function() {
      theNotificationsManager._items = exampleNotifications;
      var directive = compileDirective();
      // The directive renders an outer div for each notification.
      expect(directive.find("div > span").length).toBe(
        exampleNotifications.length,
        directive.html()
      );
      // Messages are rendered in the nested tree.
      var messages = directive
        .find("div > span > ul > li > p > span:nth-child(1)")
        .map(function() {
          return $(this).text();
        })
        .get();
      expect(messages).toEqual(
        exampleNotifications.map(function(notification) {
          return notification.message;
        })
      );
    });

    it("dismisses when dismiss link is clicked", function() {
      var notification = exampleNotifications[0];
      theNotificationsManager._items = [notification];
      var dismiss = spyOn(theNotificationsManager, "dismiss");
      var directive = compileDirective();
      directive.find("div > span > ul > li > p > a").click();
      expect(dismiss).toHaveBeenCalledWith(notification);
    });

    it("adjusts class according to category", function() {
      theNotificationsManager._items = exampleNotifications;
      var directive = compileDirective();
      var classes = directive
        .find("div > span > ul > li")
        .map(function() {
          return $(this).attr("class");
        })
        .get();
      expect(classes.length).toBe(3);
      var p_classes = [];
      angular.forEach(classes, function(cls) {
        // Find classes that begin with 'p-'.
        var matches = cls.match(/\bp-.+\b/);
        p_classes = p_classes.concat(matches);
      });
      expect(p_classes).toEqual([
        "p-notification ng-scope p-notification--negative",
        "p-notification ng-scope p-notification--caution",
        "p-notification ng-scope"
      ]);
    });

    it("adjusts class according to number in category", function() {
      // Get the message from a notification object.
      var getMessage = function(ntfn) {
        return ntfn.message;
      };
      // Is the notification object an "info" notification.
      var isInfo = function(ntfn) {
        return ntfn.category === "info";
      };
      // Find message texts rendered into the DOM.
      var findRenderedMessages = function() {
        return directive
          .find("div > span > ul > li > p > span:nth-child(1)")
          .map(function() {
            return $(this).text();
          })
          .get();
      };
      // Find grouped message texts rendered into the DOM.
      var findRenderedGroupedMessages = function() {
        return directive
          .find("div > div > ul > li > p > span:nth-child(1)")
          .map(function() {
            return $(this).text();
          })
          .get();
      };

      theNotificationsManager._items = angular.copy(exampleNotifications);
      var directive = compileDirective();

      // At first there is only one message per category.
      var messagesExpected1 = exampleNotifications.map(getMessage);
      expect(findRenderedMessages()).toEqual(messagesExpected1);

      // Now we add an additional "info" message.
      theNotificationsManager._items.push(exampleAdditionalNotification);
      $scope.$digest();

      // A category title can now be found at the point where we
      // previously found the "info" message.
      var messagesExpected2 = angular.copy(messagesExpected1);
      messagesExpected2.splice(messagesExpected2.length - 1, 1);
      expect(findRenderedMessages()).toEqual(messagesExpected2);

      // The "info" messages are now grouped.
      var groupedMessagesExpected = exampleNotifications
        .filter(isInfo)
        .map(getMessage)
        .concat([exampleAdditionalNotification.message]);
      expect(findRenderedGroupedMessages()).toEqual(groupedMessagesExpected);
    });

    it("sanitizes messages", function() {
      var harmfulNotification = angular.copy(exampleNotifications[0]);
      harmfulNotification.message =
        "Hello <script>alert('Gotcha');</script><em>World</em>!";
      theNotificationsManager._items = [harmfulNotification];
      var directive = compileDirective();
      var messages = directive.find("div > span > ul > li > p");
      expect(messages.html()).not.toContain("<script>");
      expect(messages.html()).not.toContain("Gotcha");
      expect(messages.html()).toContain("<em>World</em>");
      expect(messages.text()).toContain("Hello World!");
    });
  });
});
