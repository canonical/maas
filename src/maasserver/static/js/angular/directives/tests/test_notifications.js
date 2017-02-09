/* Copyright 2017 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for notifications directive.
 */

describe("maasNotifications", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Some example notifications as sent from the server.
    var exampleNotifications = [
        {
            "id": 1,
            "ident": null,
            "message": "Attention admins!",
            "category": "error",
            "user": null,
            "users": false,
            "admins": true,
            "created": "Fri, 27 Jan. 2017 12:19:52",
            "updated": "Fri, 27 Jan. 2017 12:19:52"
        },
        {
            "id": 2,
            "ident": null,
            "message": "Dear users, ...",
            "category": "warning",
            "user": null,
            "users": true,
            "admins": false,
            "created": "Fri, 27 Jan. 2017 12:19:52",
            "updated": "Fri, 27 Jan. 2017 12:19:52"
        },
        {
            "id": 3,
            "ident": null,
            "message": "Greetings, Individual!",
            "category": "info",
            "user": 1,
            "users": false,
            "admins": false,
            "created": "Fri, 27 Jan. 2017 12:19:52",
            "updated": "Fri, 27 Jan. 2017 12:19:52"
        }
    ];

    // Load the NotificationsManager and
    // create a new scope before each test.
    var theNotificationsManager;
    var $scope;

    beforeEach(inject(function($rootScope, NotificationsManager) {
        theNotificationsManager = NotificationsManager;
        $scope = $rootScope.$new();
    }));

    describe("maas-notifications", function() {

        // Return the compiled directive.
        function compileDirective() {
            var directive;
            var html = '<maas-notifications></maas-notifications>';

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
            expect(directive.find("div").length).toBe(
                exampleNotifications.length, directive.html());
            // Messages are rendered in the nested tree.
            var messages = directive.find(
                "div > p > span:nth-child(2)").map(
                    function() { return $(this).text(); }).get();
            expect(messages).toEqual(exampleNotifications.map(
                function(notification) { return notification.message; }));
        });

        it("dismisses when dismiss link is clicked", function() {
            var notification = exampleNotifications[0];
            theNotificationsManager._items = [notification];
            var dismiss = spyOn(theNotificationsManager, "dismiss");
            var directive = compileDirective();
            directive.find("div > p > a").click();
            expect(dismiss).toHaveBeenCalledWith(notification);
        });

        it("adjusts class according to category", function() {
            theNotificationsManager._items = exampleNotifications;
            var directive = compileDirective();
            var classes = directive.find("div").map(
                function() { return $(this).attr("class"); }).get();
            expect(classes.length).toBe(3);
            var p_classes = [];
            angular.forEach(classes, function(cls) {
                // Find classes that begin with 'p-'.
                var matches = cls.match(/\bp-.+\b/);
                p_classes = p_classes.concat(matches);
            });
            expect(p_classes).toEqual([
                "p-notification--error",
                "p-notification--warning",
                "p-notification"
            ]);
        });

        it("sanitizes messages", function() {
            var harmfulNotification = angular.copy(exampleNotifications[0]);
            harmfulNotification.message =
                "Hello <script>alert('Gotcha');</script><em>World</em>!";
            theNotificationsManager._items = [harmfulNotification];
            var directive = compileDirective();
            var messages = directive.find("div > p");
            expect(messages.html()).not.toContain("<script>");
            expect(messages.html()).not.toContain("Gotcha");
            expect(messages.html()).toContain("<em>World</em>");
            expect(messages.text()).toContain("Hello World!");
        });

    });

});
