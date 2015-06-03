/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Sticky header directive.
 *
 * Keeps the height of the header in sync with the padding-top css value on
 * maas-wrapper element.
 */


angular.module('MAAS').directive('maasStickyHeader', function() {
    return {
        restrict: "A",
        link: function(scope, element, attrs) {

            // Amount extra to add to the bottom position of the header. This
            // gives the correct spacing between the page content and the
            // header.
            var EXTRA_OFFSET = 20;

            // Current height of the header.
            var headerHeight = -1;

            // Wrapper element. Grab the element from the root element, if that
            // fails search for the element as a parent of this directives.
            var wrapperElement = angular.element(".maas-wrapper");
            if(wrapperElement.length === 0) {
                wrapperElement = element.parent(".maas-wrapper");
            }
            if(wrapperElement.length === 0) {
                throw new Error("Unable to find the maas-wrapper element.");
            }

            // Holds the number of updateBodyPadding calls that are have
            // been perfromed. The height of the element is polled every 10ms
            // for a total of 1 second after checkHeaderHeight has noticed that
            // the height of the element has changed. This is done to smooth
            // the transition as a css animiation is applied to the height
            // of the header.
            var updateCount = 0;

            // Updates the padding top for the main body, if the height is
            // different. Function uses setTimeout instead of $timeout in
            // angular because it does not require a digest cycle to run
            // after this function completes. Doing so would actually be
            // a performance hit. Timeout of 10ms was choosen because it
            // provides a smooth animation as the height of the header is
            // animated.
            var nextUpdate, updateBodyPadding;
            updateBodyPadding = function() {
                // Stop polling once the updateCount is more than 100,
                // because then a total of 1 second has passed.
                if(updateCount >= 100) {
                    updateCount = 0;
                    nextUpdate = undefined;
                    return;
                }
                updateCount++;

                // Don't update the padding-top of the main body unless the
                // height has actually changed.
                var currentHeight = element.height();
                if(headerHeight === currentHeight) {
                    nextUpdate = setTimeout(updateBodyPadding, 10);
                    return;
                }

                // Update the padding-top on the main body.
                headerHeight = currentHeight;
                var bottomOfHeader = element.offset().top + headerHeight;
                var paddingTop = bottomOfHeader + EXTRA_OFFSET;
                wrapperElement.css("padding-top", paddingTop + "px");
                nextUpdate = setTimeout(updateBodyPadding, 10);
            };

            // Called every 100ms to check if the height of the element has
            // changed. When the element height has changed the polling of
            // updateBodyPadding will occur for 1 second.
            var nextCheck, checkHeaderHeight;
            checkHeaderHeight = function() {
                // See if height has changed. If not then do nothing and
                // check in 200ms.
                var currentHeight = element.height();
                if(headerHeight === currentHeight) {
                    nextCheck = setTimeout(checkHeaderHeight, 100);
                    return;
                }

                // Header height has changed so start the polling of
                // the updateBodyPadding function.
                updateCount = 0;
                if(angular.isDefined(nextUpdate)) {
                    clearTimeout(nextUpdate);
                }
                updateBodyPadding();
                nextCheck = setTimeout(checkHeaderHeight, 100);
            };
            checkHeaderHeight();

            // Clear the timeouts and remove the padding-top on the wrapper
            // element when the scope is destroyed.
            scope.$on("$destroy", function() {
                clearTimeout(nextCheck);
                if(angular.isDefined(nextUpdate)) {
                    clearTimeout(nextUpdate);
                }
                wrapperElement.css("padding-top", "");
            });
        }
    };
});
