/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Browser Service
 *
 * Detects the browser used by the client. This is very simple case, because
 * at the moment we really only care about if the browser is Firefox. This
 * could be improved for other browsers, but this should only be used as a
 * last resort to prevent something bad happening on a misbehaving browser.
 */

/* @ngInject */
function BrowserService($window) {
  // The first items in the array will be matched first. So if the user
  // agent for the browser contains both you need to make the more
  // specific one first. E.g. Chrome contains both "Chrome" and "Safari"
  // in its user-agent string. Since "Safari" does not chrome comes first
  // so it matches that browser more specifically.
  var BROWSERS = [
    {
      name: "chrome",
      regex: /chrome/i
    },
    {
      name: "safari",
      regex: /safari/i
    },
    {
      name: "firefox",
      regex: /firefox/i
    },
    {
      name: "ie",
      regex: /MSIE/
    }
  ];

  this.browser = "other";

  // Set the browser if a regex matches. The first to match wins.
  var self = this;
  angular.forEach(BROWSERS, function(matcher) {
    if (
      matcher.regex.test($window.navigator.userAgent) &&
      self.browser === "other"
    ) {
      self.browser = matcher.name;
    }
  });
}

export default BrowserService;
