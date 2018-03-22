/*
TODO:
 - Keyboard navigation
*/


var MAASUI = MAASUI || {};

/**
 * A set of framework-agnostic JavaScript utilities for the MAAS UI
 * @namespace MAASUI.utils
 * @return {Object} public methods
 */
MAASUI.utils = (function() {
  /**
   * Run the supplied function when page content is loaded
   * @namespace MAASUI.utils
   * @method ready
   * @param {Object} fn - the function to run
   */
  var ready = function(fn) {
    if (document.attachEvent ? document.readyState === "complete" :
        document.readyState !== "loading") {
      fn();
    } else {
      document.addEventListener('DOMContentLoaded', fn);
    }
    return true;
  };

  /**
   * Toggle a specified class on the provided element
   * @namespace MAASUI.utils
   * @method toggleClass
   * @param {Object} el - a DOM element
   * @param {String} className - the class name to toggle
   * @return {bool} true for success or false if incorrect params are given
   */
  var toggleClass = function(el, className) {
    if (typeof(el) != 'undefined' && el != null) {
      if (el.classList) {
        el.classList.toggle(className);
      } else {
        var classes = el.className.split(' ');
        var existingIndex = classes.indexOf(className);
        if (existingIndex >= 0) {
          classes.splice(existingIndex, 1);
        } else {
          classes.push(className);
        }
        el.className = classes.join(' ');
      }
    } else {
      return false;
    }
    return true;
  };

  /**
   * Remove a specified class from the provided element
   * @namespace MAASUI.utils
   * @method removeClass
   * @param {Object} el - a DOM element
   * @param {String} className - the class name to remove
   * @return {bool} true for success or false if incorrect params are given
   */
  var removeClass = function(el, className) {
    if (typeof(el) != 'undefined' && el != null) {
      if (el.classList) {
        el.classList.remove(className);
      } else {
        el.className = el.className.replace(new RegExp(
          '(^|\\b)' + className.split(' ').join('|') + '(\\b|$)', 'gi'), ' ');
      }
    } else {
      return false;
    }
    return true;
  };

  /**
   * Check if a DOM element has a class
   * @namespace MAASUI.utils
   * @method hasClass
   * @param {Object} el - a DOM element
   * @param {String} className - the class name to check
   * @return {bool} is the class present
   */
  var hasClass = function(el, className) {
    var hasClass = false;

    if (el.classList) {
      hasClass = el.classList.contains(className);
    } else {
      hasClass = new RegExp(
        '(^| )' + className + '( |$)', 'gi').test(el.className);
    }

    return hasClass;
  };

  /**
   * Remove a specified class from the provided element
   * @namespace MAASUI.utils
   * @method addClass
   * @param {Object} el - a DOM element
   * @param {String} className - the class name to add
   */
  var addClass = function(el, className) {
    if (!hasClass(el, className)) {
      if (el.classList) {
        el.classList.add(className);
      } else {
        el.className += ' ' + className;
      }
    }
  };

  /**
   * Find an element's closest ancestor with a specific class
   * @namespace MAASUI.utils
   * @method findAncestor
   * @param {Object} el - a DOM element
   * @param {String} className - the class name of the ancestor to find
   */
  var findAncestor = function(el, className) {
    while ((el = el.parentElement) && !el.classList.contains(className));
    return el;
  }

  return {
    ready: ready,
    toggleClass: toggleClass,
    removeClass: removeClass,
    hasClass: hasClass,
    addClass: addClass,
    findAncestor: findAncestor
  };
})();
