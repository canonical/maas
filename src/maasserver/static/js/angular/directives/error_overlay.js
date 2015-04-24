/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Error overlay.
 *
 * Directive overrides the entire transcluded element if an error occurs or
 * connection to the region over the websocket fails or becomes disconnected.
 */

angular.module('MAAS').run(['$templateCache', function ($templateCache) {
    // Inject the error_overlay.html into the template cache.
    $templateCache.put('directive/templates/error_overlay.html', [
        '<header id="error-header" class="page-header" data-ng-show="show()">',
            '<div class="inner-wrapper">',
                '<h1 class="page-header__title eight-col">',
                    '<span class="loader" data-ng-hide="clientError"></span> ',
                    '{$ getTitle() $}',
                '</h1>',
                '<div class="page-header__actions four-col last-col">',
                    '<div class="page-header__cta two-col no-margin-bottom ',
                        'last-col">',
                        '<button class="two-col cta-ubuntu"',
                            'data-ng-click="reload()"',
                            'data-ng-show="clientError">Reload</button>',
                    '</div>',
                '</div>',
                '<div class="page-header__dropdown ng-hide" ',
                    'data-ng-show="error">',
                    '<div class="page-header__feedback">',
                        '<p class="page-header__feedback-message info">',
                            '{$ error $}',
                        '</p>',
                    '</div>',
                '</div>',
            '</div>',
        '</header>',
        '<div class="ng-hide" data-ng-hide="show()">',
            '<div ng-transclude></div>',
        '</div>'
    ].join(''));

    // Preload the svg and png error icon. Its possible that it has never been
    // loaded by the browser and if the region connection goes down and the
    // directive gets shown with an error the icon will be missing.
    //
    // Note: This is skipped if unit testing because it will throw 404 errors
    // continuously.
    if(!angular.isDefined(window.jasmine)) {
        var image = new Image();
        image.src = "static/img/icons/error.svg";
        image = new Image();
        image.src = "static/img/icons/error.png";
    }
}]);

angular.module('MAAS').directive('maasErrorOverlay', [
    '$window', '$timeout', 'RegionConnection', 'ErrorService',
    function($window, $timeout, RegionConnection, ErrorService) {
        return {
            restrict: "A",
            transclude: true,
            scope: true,
            templateUrl: 'directive/templates/error_overlay.html',
            link: function(scope, element, attrs) {

                scope.connected = false;
                scope.showDisconnected = false;
                scope.clientError = false;
                scope.wasConnected = false;

                // Holds the promise that sets showDisconnected to true. Will
                // be cleared when the scope is destroyed.
                var markDisconnected;

                // Returns true when the overlay should be shown.
                scope.show = function() {
                    // Always show if clientError.
                    if(scope.clientError) {
                        return true;
                    }
                    // Never show if connected.
                    if(scope.connected) {
                        return false;
                    }
                    // Never been connected then always show.
                    if(!scope.wasConnected) {
                        return true;
                    }
                    // Not connected.
                    return scope.showDisconnected;
                };

                // Returns the title for the header.
                scope.getTitle = function() {
                    if(scope.clientError) {
                        return "Error occurred";
                    } else if(scope.wasConnected) {
                        return "Connection lost, reconnecting...";
                    } else {
                        return "Connecting...";
                    }
                };

                // Called to reload the page.
                scope.reload = function() {
                    $window.location.reload();
                };

                // Called to when the connection status of the region
                // changes. Updates the scope connected and error values.
                var watchConnection = function() {
                    // Do nothing if already a client error.
                    if(scope.clientError) {
                        return;
                    }

                    // Set connected and the time it changed.
                    var connected = RegionConnection.isConnected();
                    if(connected !== scope.connected) {
                        scope.connected = connected;
                        if(!connected) {
                            scope.showDisconnected = false;

                            // Show disconnected after 1/2 second. This removes
                            // the flicker that can occur, if it disconnecets
                            // and reconnected quickly.
                            markDisconnected = $timeout(function() {
                                scope.showDisconnected = true;
                                markDisconnected = undefined;
                            }, 500);
                        }
                    }

                    // Set error and whether of not the connection
                    // has ever been made.
                    scope.error = RegionConnection.error;
                    if(!scope.wasConnected && connected) {
                        scope.wasConnected = true;
                    }
                };

                // Watch the isConnected and error value on the
                // RegionConnection.
                scope.$watch(function() {
                    return RegionConnection.isConnected();
                }, watchConnection);
                scope.$watch(function() {
                    return RegionConnection.error;
                }, watchConnection);

                // Called then the error value on the ErrorService changes.
                var watchError = function() {
                    var error = ErrorService._error;
                    if(angular.isString(error)) {
                        scope.clientError = true;
                        scope.error = ErrorService._error;
                    }
                };

                // Watch _error on the ErrorService.
                scope.$watch(function() {
                    return ErrorService._error;
                }, watchError);

                // Cancel the timeout on scope destroy.
                scope.$on("$destroy", function() {
                    if(angular.isDefined(markDisconnected)) {
                        $timeout.cancel(markDisconnected);
                    }
                });
            }
        };
    }]);
