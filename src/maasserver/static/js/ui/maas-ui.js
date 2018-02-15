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

  return {
    ready: ready,
    toggleClass: toggleClass,
    removeClass: removeClass,
    hasClass: hasClass,
    addClass: addClass
  };
})();

/**
 * A handler for toggleable menus
 * @namespace MAASUI.dropdown
 */
MAASUI.dropdown = (function() {
  var wrapperClassname = "p-dropdown";
  var toggleClassName = "p-dropdown__toggle";
  var menuClassName = "p-dropdown__menu";
  var menuItemClassName ="p-dropdown__item";
  var activeClassName = "active"
  var dropdowns;

  /**
   * Initialise the menu and toggle events
   * @namespace MAASUI.dropdown
   * @method init
   */
  var init = function() {
    dropdowns = document.querySelectorAll('.' + wrapperClassname);

    Array.prototype.forEach.call(dropdowns, function(dropdown, i) {
      // Add click event for dropdown toggling.
      dropdown.addEventListener("click", click);

      // Add click event to all dropdown links to close menus.
      var sublinks = dropdown.querySelectorAll('.' + menuItemClassName);
      Array.prototype.forEach.call(sublinks, function(link, i) {
        link.addEventListener("click", closeAllMenus);
      });

      // Add click event for whole document to close all menus when
      // anything else is clicked.
      document.addEventListener('click', function(event) {
        var isClickInside = dropdown.contains(event.target);
        if (!isClickInside) {
          closeAllMenus();
        }
      });
    });

    return true;
  }

  /**
   * A handler for a toggle menu click (intended for use on click events)
   * @namespace MAASUI.dropdown
   * @method click
   * @param {Object} event - a click event
   */
  var click = function(event) {
    if (MAASUI.utils.hasClass(this, activeClassName)) {
      closeAllMenus();
    } else {
      openMenu(this);
    }
    event.stopPropagation();
  }

  /**
   * Opens the menu for the provided dropdown element
   * @namespace MAASUI.dropdown
   * @method openMenu
   * @param {Object} el - the dropdown element
   */
  var openMenu = function(el) {
    closeAllMenus();
    MAASUI.utils.addClass(el, activeClassName);
  }

  /**
   * Closes all open menus and deactivates all toggles
   * @namespace MAASUI.dropdown
   * @method closeAllMenus
   * @param {Object} event - a click event (optional)
   */
  var closeAllMenus = function(event) {
    Array.prototype.forEach.call(dropdowns, function(dropdown, i) {
      //Deactive all toggle buttons
      MAASUI.utils.removeClass(dropdown, activeClassName);
    });

    if (typeof event != 'undefined') {
      event.stopPropagation();
    }
  }

  return {
    init: init
  };
})();

MAASUI.utils.ready(MAASUI.dropdown.init);
