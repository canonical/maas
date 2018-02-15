/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Accordion directive.
 *
 * Provides an accordion effect to an element with maas-accordion class and
 * all child elements with maas-accordion-tab. Only one accordion tab is open
 * at a time, selecting another accordion will set "active" on that
 * accordion tab.
 */


 angular.module('MAAS').directive('maasCodeLines', function () {
     return {
         restrict: "A",
         scope: {
             maasCodeLines: '&'
         },
         link: function(scope, element, attributes) {

             function insertContent() {

                 // Empty the element contents and include again, this asures
                 // its the most up-to-date content
                 element.empty();
                 element.text(scope.maasCodeLines);

                 // Count the line contents
                 var lines = element.html().split('\n'),
                     insert = "<code>";

                 // Each line is to be wrapped by a span which is style & given
                 // its appropriate line number
                 $.each(lines, function() {
                   insert += '<span class="code-line">' +
                   this + '</span>';
                 });
                 insert += "</code>";

                 // Re-insert the contents
                 element.html(insert);
             }

             // Watch the contents of the element so when it changes to
             // re-add the line numbers.
             scope.$watch(scope.maasCodeLines, insertContent);
         }
     };
 });
