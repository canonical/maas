/******/ (function(modules) { // webpackBootstrap
/******/ 	// The module cache
/******/ 	var installedModules = {};
/******/
/******/ 	// The require function
/******/ 	function __webpack_require__(moduleId) {
/******/
/******/ 		// Check if module is in cache
/******/ 		if(installedModules[moduleId]) {
/******/ 			return installedModules[moduleId].exports;
/******/ 		}
/******/ 		// Create a new module (and put it into the cache)
/******/ 		var module = installedModules[moduleId] = {
/******/ 			i: moduleId,
/******/ 			l: false,
/******/ 			exports: {}
/******/ 		};
/******/
/******/ 		// Execute the module function
/******/ 		modules[moduleId].call(module.exports, module, module.exports, __webpack_require__);
/******/
/******/ 		// Flag the module as loaded
/******/ 		module.l = true;
/******/
/******/ 		// Return the exports of the module
/******/ 		return module.exports;
/******/ 	}
/******/
/******/
/******/ 	// expose the modules object (__webpack_modules__)
/******/ 	__webpack_require__.m = modules;
/******/
/******/ 	// expose the module cache
/******/ 	__webpack_require__.c = installedModules;
/******/
/******/ 	// define getter function for harmony exports
/******/ 	__webpack_require__.d = function(exports, name, getter) {
/******/ 		if(!__webpack_require__.o(exports, name)) {
/******/ 			Object.defineProperty(exports, name, { enumerable: true, get: getter });
/******/ 		}
/******/ 	};
/******/
/******/ 	// define __esModule on exports
/******/ 	__webpack_require__.r = function(exports) {
/******/ 		if(typeof Symbol !== 'undefined' && Symbol.toStringTag) {
/******/ 			Object.defineProperty(exports, Symbol.toStringTag, { value: 'Module' });
/******/ 		}
/******/ 		Object.defineProperty(exports, '__esModule', { value: true });
/******/ 	};
/******/
/******/ 	// create a fake namespace object
/******/ 	// mode & 1: value is a module id, require it
/******/ 	// mode & 2: merge all properties of value into the ns
/******/ 	// mode & 4: return value when already ns object
/******/ 	// mode & 8|1: behave like require
/******/ 	__webpack_require__.t = function(value, mode) {
/******/ 		if(mode & 1) value = __webpack_require__(value);
/******/ 		if(mode & 8) return value;
/******/ 		if((mode & 4) && typeof value === 'object' && value && value.__esModule) return value;
/******/ 		var ns = Object.create(null);
/******/ 		__webpack_require__.r(ns);
/******/ 		Object.defineProperty(ns, 'default', { enumerable: true, value: value });
/******/ 		if(mode & 2 && typeof value != 'string') for(var key in value) __webpack_require__.d(ns, key, function(key) { return value[key]; }.bind(null, key));
/******/ 		return ns;
/******/ 	};
/******/
/******/ 	// getDefaultExport function for compatibility with non-harmony modules
/******/ 	__webpack_require__.n = function(module) {
/******/ 		var getter = module && module.__esModule ?
/******/ 			function getDefault() { return module['default']; } :
/******/ 			function getModuleExports() { return module; };
/******/ 		__webpack_require__.d(getter, 'a', getter);
/******/ 		return getter;
/******/ 	};
/******/
/******/ 	// Object.prototype.hasOwnProperty.call
/******/ 	__webpack_require__.o = function(object, property) { return Object.prototype.hasOwnProperty.call(object, property); };
/******/
/******/ 	// __webpack_public_path__
/******/ 	__webpack_require__.p = "";
/******/
/******/
/******/ 	// Load entry module and return exports
/******/ 	return __webpack_require__(__webpack_require__.s = 197);
/******/ })
/************************************************************************/
/******/ ({

/***/ 197:
/***/ (function(module, exports, __webpack_require__) {

__webpack_require__(198);
module.exports = __webpack_require__(199);


/***/ }),

/***/ 198:
/***/ (function(module, exports, __webpack_require__) {

"use strict";


/*!
 * ngTagsInput v2.3.0
 * http://mbenford.github.io/ngTagsInput
 *
 * Copyright (c) 2013-2015 Michael Benford
 * License: MIT
 *
 * Generated at 2015-03-24 00:49:44 -0300
 */
(function () {
  'use strict';

  var KEYS = {
    backspace: 8,
    tab: 9,
    enter: 13,
    escape: 27,
    space: 32,
    up: 38,
    down: 40,
    left: 37,
    right: 39,
    delete: 46,
    comma: 188
  };
  var MAX_SAFE_INTEGER = 9007199254740991;
  var SUPPORTED_INPUT_TYPES = ['text', 'email', 'url'];
  var tagsInput = angular.module('ngTagsInput', []);
  /**
   * @ngdoc directive
   * @name tagsInput
   * @module ngTagsInput
   *
   * @description
   * Renders an input box with tag editing support.
   *
   * @param {string} ngModel Assignable angular expression to data-bind to.
   * @param {string=} [displayProperty=text] Property to be rendered as the tag label.
   * @param {string=} [keyProperty=text] Property to be used as a unique identifier for the tag.
   * @param {string=} [type=text] Type of the input element. Only 'text', 'email' and 'url' are supported values.
   * @param {number=} tabindex Tab order of the control.
   * @param {string=} [placeholder=Add a tag] Placeholder text for the control.
   * @param {number=} [minLength=3] Minimum length for a new tag.
   * @param {number=} [maxLength=MAX_SAFE_INTEGER] Maximum length allowed for a new tag.
   * @param {number=} [minTags=0] Sets minTags validation error key if the number of tags added is less than minTags.
   * @param {number=} [maxTags=MAX_SAFE_INTEGER] Sets maxTags validation error key if the number of tags added is greater than maxTags.
   * @param {boolean=} [allowLeftoverText=false] Sets leftoverText validation error key if there is any leftover text in
   *                                             the input element when the directive loses focus.
   * @param {string=} [removeTagSymbol=×] Symbol character for the remove tag button.
   * @param {boolean=} [addOnEnter=true] Flag indicating that a new tag will be added on pressing the ENTER key.
   * @param {boolean=} [addOnSpace=false] Flag indicating that a new tag will be added on pressing the SPACE key.
   * @param {boolean=} [addOnComma=true] Flag indicating that a new tag will be added on pressing the COMMA key.
   * @param {boolean=} [addOnBlur=true] Flag indicating that a new tag will be added when the input field loses focus.
   * @param {boolean=} [addOnPaste=false] Flag indicating that the text pasted into the input field will be split into tags.
   * @param {string=} [pasteSplitPattern=,] Regular expression used to split the pasted text into tags.
   * @param {boolean=} [replaceSpacesWithDashes=true] Flag indicating that spaces will be replaced with dashes.
   * @param {string=} [allowedTagsPattern=.+] Regular expression that determines whether a new tag is valid.
   * @param {boolean=} [enableEditingLastTag=false] Flag indicating that the last tag will be moved back into
   *                                                the new tag input box instead of being removed when the backspace key
   *                                                is pressed and the input box is empty.
   * @param {boolean=} [addFromAutocompleteOnly=false] Flag indicating that only tags coming from the autocomplete list will be allowed.
   *                                                   When this flag is true, addOnEnter, addOnComma, addOnSpace, addOnBlur and
   *                                                   allowLeftoverText values are ignored.
   * @param {boolean=} [spellcheck=true] Flag indicating whether the browser's spellcheck is enabled for the input field or not.
   * @param {expression} onTagAdding Expression to evaluate that will be invoked before adding a new tag. The new tag is available as $tag. This method must return either true or false. If false, the tag will not be added.
   * @param {expression} onTagAdded Expression to evaluate upon adding a new tag. The new tag is available as $tag.
   * @param {expression} onInvalidTag Expression to evaluate when a tag is invalid. The invalid tag is available as $tag.
   * @param {expression} onTagRemoving Expression to evaluate that will be invoked before removing a tag. The tag is available as $tag. This method must return either true or false. If false, the tag will not be removed.
   * @param {expression} onTagRemoved Expression to evaluate upon removing an existing tag. The removed tag is available as $tag.
   */

  tagsInput.directive('tagsInput', ["$timeout", "$document", "$window", "tagsInputConfig", "tiUtil", function ($timeout, $document, $window, tagsInputConfig, tiUtil) {
    function TagList(options, events, onTagAdding, onTagRemoving) {
      var self = {},
          getTagText,
          setTagText,
          tagIsValid;

      getTagText = function getTagText(tag) {
        return tiUtil.safeToString(tag[options.displayProperty]);
      };

      setTagText = function setTagText(tag, text) {
        tag[options.displayProperty] = text;
      };

      tagIsValid = function tagIsValid(tag) {
        var tagText = getTagText(tag);
        return tagText && tagText.length >= options.minLength && tagText.length <= options.maxLength && options.allowedTagsPattern.test(tagText) && !tiUtil.findInObjectArray(self.items, tag, options.keyProperty || options.displayProperty) && onTagAdding({
          $tag: tag
        });
      };

      self.items = [];

      self.addText = function (text) {
        var tag = {};
        setTagText(tag, text);
        return self.add(tag);
      };

      self.add = function (tag) {
        var tagText = getTagText(tag);

        if (options.replaceSpacesWithDashes) {
          tagText = tiUtil.replaceSpacesWithDashes(tagText);
        }

        setTagText(tag, tagText);

        if (tagIsValid(tag)) {
          self.items.push(tag);
          events.trigger('tag-added', {
            $tag: tag
          });
        } else if (tagText) {
          events.trigger('invalid-tag', {
            $tag: tag
          });
        }

        return tag;
      };

      self.remove = function (index) {
        var tag = self.items[index];

        if (onTagRemoving({
          $tag: tag
        })) {
          self.items.splice(index, 1);
          self.clearSelection();
          events.trigger('tag-removed', {
            $tag: tag
          });
          return tag;
        }
      };

      self.select = function (index) {
        if (index < 0) {
          index = self.items.length - 1;
        } else if (index >= self.items.length) {
          index = 0;
        }

        self.index = index;
        self.selected = self.items[index];
      };

      self.selectPrior = function () {
        self.select(--self.index);
      };

      self.selectNext = function () {
        self.select(++self.index);
      };

      self.removeSelected = function () {
        return self.remove(self.index);
      };

      self.clearSelection = function () {
        self.selected = null;
        self.index = -1;
      };

      self.clearSelection();
      return self;
    }

    function validateType(type) {
      return SUPPORTED_INPUT_TYPES.indexOf(type) !== -1;
    }

    return {
      restrict: 'E',
      require: 'ngModel',
      scope: {
        tags: '=ngModel',
        onTagAdding: '&',
        onTagAdded: '&',
        onInvalidTag: '&',
        onTagRemoving: '&',
        onTagRemoved: '&'
      },
      replace: false,
      transclude: true,
      templateUrl: 'ngTagsInput/tags-input.html',
      controller: ["$scope", "$attrs", "$element", function ($scope, $attrs, $element) {
        $scope.events = tiUtil.simplePubSub();
        tagsInputConfig.load('tagsInput', $scope, $attrs, {
          template: [String, 'ngTagsInput/tag-item.html'],
          type: [String, 'text', validateType],
          placeholder: [String, 'Add a tag'],
          tabindex: [Number, null],
          removeTagSymbol: [String, String.fromCharCode(215)],
          replaceSpacesWithDashes: [Boolean, true],
          minLength: [Number, 3],
          maxLength: [Number, MAX_SAFE_INTEGER],
          addOnEnter: [Boolean, true],
          addOnSpace: [Boolean, false],
          addOnComma: [Boolean, true],
          addOnBlur: [Boolean, true],
          addOnPaste: [Boolean, false],
          pasteSplitPattern: [RegExp, /,/],
          allowedTagsPattern: [RegExp, /.+/],
          enableEditingLastTag: [Boolean, false],
          minTags: [Number, 0],
          maxTags: [Number, MAX_SAFE_INTEGER],
          displayProperty: [String, 'text'],
          keyProperty: [String, ''],
          allowLeftoverText: [Boolean, false],
          addFromAutocompleteOnly: [Boolean, false],
          spellcheck: [Boolean, true]
        });
        $scope.tagList = new TagList($scope.options, $scope.events, tiUtil.handleUndefinedResult($scope.onTagAdding, true), tiUtil.handleUndefinedResult($scope.onTagRemoving, true));

        this.registerAutocomplete = function () {
          var input = $element.find('input');
          return {
            addTag: function addTag(tag) {
              return $scope.tagList.add(tag);
            },
            focusInput: function focusInput() {// blake_r - Stop the focus as this breaks on the
              // version of AngularJS that ships with MAAS.
              //input[0].focus();
            },
            getTags: function getTags() {
              return $scope.tags;
            },
            getCurrentTagText: function getCurrentTagText() {
              return $scope.newTag.text;
            },
            getOptions: function getOptions() {
              return $scope.options;
            },
            on: function on(name, handler) {
              $scope.events.on(name, handler);
              return this;
            }
          };
        };

        this.registerTagItem = function () {
          return {
            getOptions: function getOptions() {
              return $scope.options;
            },
            removeTag: function removeTag(index) {
              if ($scope.disabled) {
                return;
              }

              $scope.tagList.remove(index);
            }
          };
        };
      }],
      link: function link(scope, element, attrs, ngModelCtrl) {
        var hotkeys = [KEYS.enter, KEYS.comma, KEYS.space, KEYS.backspace, KEYS.delete, KEYS.left, KEYS.right],
            tagList = scope.tagList,
            events = scope.events,
            options = scope.options,
            input = element.find('input'),
            validationOptions = ['minTags', 'maxTags', 'allowLeftoverText'],
            setElementValidity;

        setElementValidity = function setElementValidity() {
          ngModelCtrl.$setValidity('maxTags', scope.tags.length <= options.maxTags);
          ngModelCtrl.$setValidity('minTags', scope.tags.length >= options.minTags);
          ngModelCtrl.$setValidity('leftoverText', scope.hasFocus || options.allowLeftoverText ? true : !scope.newTag.text);
        };

        ngModelCtrl.$isEmpty = function (value) {
          return !value || !value.length;
        };

        scope.newTag = {
          text: '',
          invalid: null,
          setText: function setText(value) {
            this.text = value;
            events.trigger('input-change', value);
          }
        };

        scope.track = function (tag) {
          return tag[options.keyProperty || options.displayProperty];
        };

        scope.$watch('tags', function (value) {
          scope.tags = tiUtil.makeObjectArray(value, options.displayProperty);
          tagList.items = scope.tags;
        });
        scope.$watch('tags.length', function () {
          setElementValidity();
        });
        attrs.$observe('disabled', function (value) {
          scope.disabled = value;
        });
        scope.eventHandlers = {
          input: {
            change: function change(text) {
              events.trigger('input-change', text);
            },
            keydown: function keydown($event) {
              events.trigger('input-keydown', $event);
            },
            focus: function focus() {
              if (scope.hasFocus) {
                return;
              }

              scope.hasFocus = true;
              events.trigger('input-focus');
            },
            blur: function blur() {
              $timeout(function () {
                var activeElement = $document.prop('activeElement'),
                    lostFocusToBrowserWindow = activeElement === input[0],
                    lostFocusToChildElement = element[0].contains(activeElement);

                if (lostFocusToBrowserWindow || !lostFocusToChildElement) {
                  scope.hasFocus = false;
                  events.trigger('input-blur');
                }
              });
            },
            paste: function paste($event) {
              $event.getTextData = function () {
                var clipboardData = $event.clipboardData || $event.originalEvent && $event.originalEvent.clipboardData;
                return clipboardData ? clipboardData.getData('text/plain') : $window.clipboardData.getData('Text');
              };

              events.trigger('input-paste', $event);
            }
          },
          host: {
            click: function click() {
              if (scope.disabled) {
                return;
              } // blake_r - Stop the focus as this breaks on the
              // version of AngularJS that ships with MAAS.
              //input[0].focus();

            }
          }
        };
        events.on('tag-added', scope.onTagAdded).on('invalid-tag', scope.onInvalidTag).on('tag-removed', scope.onTagRemoved).on('tag-added', function () {
          scope.newTag.setText('');
        }).on('tag-added tag-removed', function () {
          // Sets the element to its dirty state
          // In Angular 1.3 this will be replaced with $setDirty.
          ngModelCtrl.$setViewValue(scope.tags);
        }).on('invalid-tag', function () {
          scope.newTag.invalid = true;
        }).on('option-change', function (e) {
          if (validationOptions.indexOf(e.name) !== -1) {
            setElementValidity();
          }
        }).on('input-change', function () {
          tagList.clearSelection();
          scope.newTag.invalid = null;
        }).on('input-focus', function () {
          element.triggerHandler('focus');
          ngModelCtrl.$setValidity('leftoverText', true);
        }).on('input-blur', function () {
          if (options.addOnBlur && !options.addFromAutocompleteOnly) {
            tagList.addText(scope.newTag.text);
          }

          element.triggerHandler('blur');
          setElementValidity();
        }).on('input-keydown', function (event) {
          var key = event.keyCode,
              isModifier = event.shiftKey || event.altKey || event.ctrlKey || event.metaKey,
              addKeys = {},
              shouldAdd,
              shouldRemove,
              shouldSelect,
              shouldEditLastTag;

          if (isModifier || hotkeys.indexOf(key) === -1) {
            return;
          }

          addKeys[KEYS.enter] = options.addOnEnter;
          addKeys[KEYS.comma] = options.addOnComma;
          addKeys[KEYS.space] = options.addOnSpace;
          shouldAdd = !options.addFromAutocompleteOnly && addKeys[key];
          shouldRemove = (key === KEYS.backspace || key === KEYS.delete) && tagList.selected;
          shouldEditLastTag = key === KEYS.backspace && scope.newTag.text.length === 0 && options.enableEditingLastTag;
          shouldSelect = (key === KEYS.backspace || key === KEYS.left || key === KEYS.right) && scope.newTag.text.length === 0 && !options.enableEditingLastTag;

          if (shouldAdd) {
            tagList.addText(scope.newTag.text);
          } else if (shouldEditLastTag) {
            var tag;
            tagList.selectPrior();
            tag = tagList.removeSelected();

            if (tag) {
              scope.newTag.setText(tag[options.displayProperty]);
            }
          } else if (shouldRemove) {
            tagList.removeSelected();
          } else if (shouldSelect) {
            if (key === KEYS.left || key === KEYS.backspace) {
              tagList.selectPrior();
            } else if (key === KEYS.right) {
              tagList.selectNext();
            }
          }

          if (shouldAdd || shouldSelect || shouldRemove || shouldEditLastTag) {
            event.preventDefault();
          }
        }).on('input-paste', function (event) {
          if (options.addOnPaste) {
            var data = event.getTextData();
            var tags = data.split(options.pasteSplitPattern);

            if (tags.length > 1) {
              tags.forEach(function (tag) {
                tagList.addText(tag);
              });
              event.preventDefault();
            }
          }
        });
      }
    };
  }]);
  /**
   * @ngdoc directive
   * @name tiTagItem
   * @module ngTagsInput
   *
   * @description
   * Represents a tag item. Used internally by the tagsInput directive.
   */

  tagsInput.directive('tiTagItem', ["tiUtil", function (tiUtil) {
    return {
      restrict: 'E',
      require: '^tagsInput',
      template: '<ng-include src="$$template"></ng-include>',
      scope: {
        data: '='
      },
      link: function link(scope, element, attrs, tagsInputCtrl) {
        var tagsInput = tagsInputCtrl.registerTagItem(),
            options = tagsInput.getOptions();
        scope.$$template = options.template;
        scope.$$removeTagSymbol = options.removeTagSymbol;

        scope.$getDisplayText = function () {
          return tiUtil.safeToString(scope.data[options.displayProperty]);
        };

        scope.$removeTag = function () {
          tagsInput.removeTag(scope.$index);
        };

        scope.$watch('$parent.$index', function (value) {
          scope.$index = value;
        });
      }
    };
  }]);
  /**
   * @ngdoc directive
   * @name autoComplete
   * @module ngTagsInput
   *
   * @description
   * Provides autocomplete support for the tagsInput directive.
   *
   * @param {expression} source Expression to evaluate upon changing the input content. The input value is available as
   *                            $query. The result of the expression must be a promise that eventually resolves to an
   *                            array of strings.
   * @param {string=} [displayProperty=text] Property to be rendered as the autocomplete label.
   * @param {number=} [debounceDelay=100] Amount of time, in milliseconds, to wait before evaluating the expression in
   *                                      the source option after the last keystroke.
   * @param {number=} [minLength=3] Minimum number of characters that must be entered before evaluating the expression
   *                                 in the source option.
   * @param {boolean=} [highlightMatchedText=true] Flag indicating that the matched text will be highlighted in the
   *                                               suggestions list.
   * @param {number=} [maxResultsToShow=10] Maximum number of results to be displayed at a time.
   * @param {boolean=} [loadOnDownArrow=false] Flag indicating that the source option will be evaluated when the down arrow
   *                                           key is pressed and the suggestion list is closed. The current input value
   *                                           is available as $query.
   * @param {boolean=} {loadOnEmpty=false} Flag indicating that the source option will be evaluated when the input content
   *                                       becomes empty. The $query variable will be passed to the expression as an empty string.
   * @param {boolean=} {loadOnFocus=false} Flag indicating that the source option will be evaluated when the input element
   *                                       gains focus. The current input value is available as $query.
   * @param {boolean=} [selectFirstMatch=true] Flag indicating that the first match will be automatically selected once
   *                                           the suggestion list is shown.
   * @param {string=} [template=] URL or id of a custom template for rendering each element of the autocomplete list.
   */

  tagsInput.directive('autoComplete', ["$document", "$timeout", "$sce", "$q", "tagsInputConfig", "tiUtil", function ($document, $timeout, $sce, $q, tagsInputConfig, tiUtil) {
    function SuggestionList(loadFn, options, events) {
      var self = {},
          getDifference,
          lastPromise,
          getTagId;

      getTagId = function getTagId() {
        return options.tagsInput.keyProperty || options.tagsInput.displayProperty;
      };

      getDifference = function getDifference(array1, array2) {
        return array1.filter(function (item) {
          return !tiUtil.findInObjectArray(array2, item, getTagId(), function (a, b) {
            if (options.tagsInput.replaceSpacesWithDashes) {
              a = tiUtil.replaceSpacesWithDashes(a);
              b = tiUtil.replaceSpacesWithDashes(b);
            }

            return tiUtil.defaultComparer(a, b);
          });
        });
      };

      self.reset = function () {
        lastPromise = null;
        self.items = [];
        self.visible = false;
        self.index = -1;
        self.selected = null;
        self.query = null;
      };

      self.show = function () {
        if (options.selectFirstMatch) {
          self.select(0);
        } else {
          self.selected = null;
        }

        self.visible = true;
      };

      self.load = tiUtil.debounce(function (query, tags) {
        self.query = query;
        var promise = $q.when(loadFn({
          $query: query
        }));
        lastPromise = promise;
        promise.then(function (items) {
          if (promise !== lastPromise) {
            return;
          }

          items = tiUtil.makeObjectArray(items.data || items, getTagId());
          items = getDifference(items, tags);
          self.items = items.slice(0, options.maxResultsToShow);

          if (self.items.length > 0) {
            self.show();
          } else {
            self.reset();
          }
        });
      }, options.debounceDelay);

      self.selectNext = function () {
        self.select(++self.index);
      };

      self.selectPrior = function () {
        self.select(--self.index);
      };

      self.select = function (index) {
        if (index < 0) {
          index = self.items.length - 1;
        } else if (index >= self.items.length) {
          index = 0;
        }

        self.index = index;
        self.selected = self.items[index];
        events.trigger('suggestion-selected', index);
      };

      self.reset();
      return self;
    }

    function scrollToElement(root, index) {
      var element = root.find('li').eq(index),
          parent = element.parent(),
          elementTop = element.prop('offsetTop'),
          elementHeight = element.prop('offsetHeight'),
          parentHeight = parent.prop('clientHeight'),
          parentScrollTop = parent.prop('scrollTop');

      if (elementTop < parentScrollTop) {
        parent.prop('scrollTop', elementTop);
      } else if (elementTop + elementHeight > parentHeight + parentScrollTop) {
        parent.prop('scrollTop', elementTop + elementHeight - parentHeight);
      }
    }

    return {
      restrict: 'E',
      require: '^tagsInput',
      scope: {
        source: '&'
      },
      templateUrl: 'ngTagsInput/auto-complete.html',
      controller: ["$scope", "$element", "$attrs", function ($scope, $element, $attrs) {
        $scope.events = tiUtil.simplePubSub();
        tagsInputConfig.load('autoComplete', $scope, $attrs, {
          template: [String, 'ngTagsInput/auto-complete-match.html'],
          debounceDelay: [Number, 100],
          minLength: [Number, 3],
          highlightMatchedText: [Boolean, true],
          maxResultsToShow: [Number, 10],
          loadOnDownArrow: [Boolean, false],
          loadOnEmpty: [Boolean, false],
          loadOnFocus: [Boolean, false],
          selectFirstMatch: [Boolean, true],
          displayProperty: [String, '']
        });
        $scope.suggestionList = new SuggestionList($scope.source, $scope.options, $scope.events);

        $scope.getCurrentTag = function () {
          return $scope.$parent.$parent.newTag.text;
        };

        $scope.addTag = function (tag) {
          $scope.$parent.$parent.tagList.items.push({
            text: tag
          });
          $scope.$parent.$parent.newTag.setText('');
        };

        this.registerAutocompleteMatch = function () {
          return {
            getOptions: function getOptions() {
              return $scope.options;
            },
            getQuery: function getQuery() {
              return $scope.suggestionList.query;
            }
          };
        };
      }],
      link: function link(scope, element, attrs, tagsInputCtrl) {
        var hotkeys = [KEYS.enter, KEYS.tab, KEYS.escape, KEYS.up, KEYS.down],
            suggestionList = scope.suggestionList,
            tagsInput = tagsInputCtrl.registerAutocomplete(),
            options = scope.options,
            events = scope.events,
            shouldLoadSuggestions;
        options.tagsInput = tagsInput.getOptions();

        shouldLoadSuggestions = function shouldLoadSuggestions(value) {
          return value && value.length >= options.minLength || !value && options.loadOnEmpty;
        };

        scope.addSuggestionByIndex = function (index) {
          suggestionList.select(index);
          scope.addSuggestion();
        };

        scope.addSuggestion = function () {
          var added = false;

          if (suggestionList.selected) {
            tagsInput.addTag(angular.copy(suggestionList.selected));
            suggestionList.reset();
            tagsInput.focusInput();
            added = true;
          }

          return added;
        };

        scope.track = function (item) {
          return item[options.tagsInput.keyProperty || options.tagsInput.displayProperty];
        };

        tagsInput.on('tag-added invalid-tag input-blur', function () {
          suggestionList.reset();
        }).on('input-change', function (value) {
          if (shouldLoadSuggestions(value)) {
            suggestionList.load(value, tagsInput.getTags());
          } else {
            suggestionList.reset();
          }
        }).on('input-focus', function () {
          var value = tagsInput.getCurrentTagText();
          scope.hasFocus = true;
          scope.shouldLoadSuggestions = shouldLoadSuggestions(value);

          if (options.loadOnFocus && scope.shouldLoadSuggestions) {
            suggestionList.load(value, tagsInput.getTags());
          }
        }).on('input-keydown', function (event) {
          var key = event.keyCode,
              handled = false;

          if (hotkeys.indexOf(key) === -1) {
            return;
          }

          if (suggestionList.visible) {
            if (key === KEYS.down) {
              suggestionList.selectNext();
              handled = true;
            } else if (key === KEYS.up) {
              suggestionList.selectPrior();
              handled = true;
            } else if (key === KEYS.escape) {
              suggestionList.reset();
              handled = true;
            } else if (key === KEYS.enter || key === KEYS.tab) {
              handled = scope.addSuggestion();
            }
          } else {
            if (key === KEYS.down && scope.options.loadOnDownArrow) {
              suggestionList.load(tagsInput.getCurrentTagText(), tagsInput.getTags());
              handled = true;
            }
          }

          if (handled) {
            event.preventDefault();
            event.stopImmediatePropagation();
            return false;
          }
        }).on('input-blur', function () {
          scope.hasFocus = false;
        });
        events.on('suggestion-selected', function (index) {
          scrollToElement(element, index);
        });
      }
    };
  }]);
  /**
   * @ngdoc directive
   * @name tiAutocompleteMatch
   * @module ngTagsInput
   *
   * @description
   * Represents an autocomplete match. Used internally by the autoComplete directive.
   */

  tagsInput.directive('tiAutocompleteMatch', ["$sce", "tiUtil", function ($sce, tiUtil) {
    return {
      restrict: 'E',
      require: '^autoComplete',
      template: '<ng-include src="$$template"></ng-include>',
      scope: {
        data: '='
      },
      link: function link(scope, element, attrs, autoCompleteCtrl) {
        var autoComplete = autoCompleteCtrl.registerAutocompleteMatch(),
            options = autoComplete.getOptions();
        scope.$$template = options.template;
        scope.$index = scope.$parent.$index;

        scope.$highlight = function (text) {
          if (options.highlightMatchedText) {
            text = tiUtil.safeHighlight(text, autoComplete.getQuery());
          }

          return $sce.trustAsHtml(text);
        };

        scope.$getDisplayText = function () {
          return tiUtil.safeToString(scope.data[options.displayProperty || options.tagsInput.displayProperty]);
        };
      }
    };
  }]);
  /**
   * @ngdoc directive
   * @name tiTranscludeAppend
   * @module ngTagsInput
   *
   * @description
   * Re-creates the old behavior of ng-transclude. Used internally by tagsInput directive.
   */

  tagsInput.directive('tiTranscludeAppend', function () {
    return function (scope, element, attrs, ctrl, transcludeFn) {
      transcludeFn(function (clone) {
        element.append(clone);
      });
    };
  });
  /**
   * @ngdoc directive
   * @name tiAutosize
   * @module ngTagsInput
   *
   * @description
   * Automatically sets the input's width so its content is always visible. Used internally by tagsInput directive.
   */

  tagsInput.directive('tiAutosize', ["tagsInputConfig", function (tagsInputConfig) {
    return {
      restrict: 'A',
      require: 'ngModel',
      link: function link(scope, element, attrs, ctrl) {
        var threshold = tagsInputConfig.getTextAutosizeThreshold(),
            span,
            resize;
        span = angular.element('<span class="input"></span>');
        span.css('display', 'none').css('visibility', 'hidden').css('width', 'auto').css('white-space', 'pre');
        element.parent().append(span);

        resize = function resize(originalValue) {
          var value = originalValue,
              width;

          if (angular.isString(value) && value.length === 0) {
            value = attrs.placeholder;
          }

          if (value) {
            span.text(value);
            span.css('display', '');
            width = span.prop('offsetWidth');
            span.css('display', 'none');
          }

          element.css('width', width ? width + threshold + 'px' : '');
          return originalValue;
        };

        ctrl.$parsers.unshift(resize);
        ctrl.$formatters.unshift(resize);
        attrs.$observe('placeholder', function (value) {
          if (!ctrl.$modelValue) {
            resize(value);
          }
        });
      }
    };
  }]);
  /**
   * @ngdoc directive
   * @name tiBindAttrs
   * @module ngTagsInput
   *
   * @description
   * Binds attributes to expressions. Used internally by tagsInput directive.
   */

  tagsInput.directive('tiBindAttrs', function () {
    return function (scope, element, attrs) {
      scope.$watch(attrs.tiBindAttrs, function (value) {
        angular.forEach(value, function (value, key) {
          /**
           * blake_r - Added to work around the version of jQuery that
           * MAAS currently ships with. Once packaging for jQuery is
           * version >1.9 this can be removed.
           */
          if (key === "type") {
            element[0].type = value;
          } else {
            attrs.$set(key, value);
          }
        });
      }, true);
    };
  });
  /**
   * @ngdoc service
   * @name tagsInputConfig
   * @module ngTagsInput
   *
   * @description
   * Sets global configuration settings for both tagsInput and autoComplete directives. It's also used internally to parse and
   * initialize options from HTML attributes.
   */

  tagsInput.provider('tagsInputConfig', function () {
    var globalDefaults = {},
        interpolationStatus = {},
        autosizeThreshold = 3;
    /**
     * @ngdoc method
     * @name setDefaults
     * @description Sets the default configuration option for a directive.
     * @methodOf tagsInputConfig
     *
     * @param {string} directive Name of the directive to be configured. Must be either 'tagsInput' or 'autoComplete'.
     * @param {object} defaults Object containing options and their values.
     *
     * @returns {object} The service itself for chaining purposes.
     */

    this.setDefaults = function (directive, defaults) {
      globalDefaults[directive] = defaults;
      return this;
    };
    /***
     * @ngdoc method
     * @name setActiveInterpolation
     * @description Sets active interpolation for a set of options.
     * @methodOf tagsInputConfig
     *
     * @param {string} directive Name of the directive to be configured. Must be either 'tagsInput' or 'autoComplete'.
     * @param {object} options Object containing which options should have interpolation turned on at all times.
     *
     * @returns {object} The service itself for chaining purposes.
     */


    this.setActiveInterpolation = function (directive, options) {
      interpolationStatus[directive] = options;
      return this;
    };
    /***
     * @ngdoc method
     * @name setTextAutosizeThreshold
     * @description Sets the threshold used by the tagsInput directive to re-size the inner input field element based on its contents.
     * @methodOf tagsInputConfig
     *
     * @param {number} threshold Threshold value, in pixels.
     *
     * @returns {object} The service itself for chaining purposes.
     */


    this.setTextAutosizeThreshold = function (threshold) {
      autosizeThreshold = threshold;
      return this;
    };

    this.$get = ["$interpolate", function ($interpolate) {
      var converters = {};

      converters[String] = function (value) {
        return value;
      };

      converters[Number] = function (value) {
        return parseInt(value, 10);
      };

      converters[Boolean] = function (value) {
        return value.toLowerCase() === 'true';
      };

      converters[RegExp] = function (value) {
        return new RegExp(value);
      };

      return {
        load: function load(directive, scope, attrs, options) {
          var defaultValidator = function defaultValidator() {
            return true;
          };

          scope.options = {};
          angular.forEach(options, function (value, key) {
            var type, localDefault, validator, converter, getDefault, updateValue;
            type = value[0];
            localDefault = value[1];
            validator = value[2] || defaultValidator;
            converter = converters[type];

            getDefault = function getDefault() {
              var globalValue = globalDefaults[directive] && globalDefaults[directive][key];
              return angular.isDefined(globalValue) ? globalValue : localDefault;
            };

            updateValue = function updateValue(value) {
              scope.options[key] = value && validator(value) ? converter(value) : getDefault();
            };

            if (interpolationStatus[directive] && interpolationStatus[directive][key]) {
              attrs.$observe(key, function (value) {
                updateValue(value);
                scope.events.trigger('option-change', {
                  name: key,
                  newValue: value
                });
              });
            } else {
              updateValue(attrs[key] && $interpolate(attrs[key])(scope.$parent));
            }
          });
        },
        getTextAutosizeThreshold: function getTextAutosizeThreshold() {
          return autosizeThreshold;
        }
      };
    }];
  });
  /***
   * @ngdoc factory
   * @name tiUtil
   * @module ngTagsInput
   *
   * @description
   * Helper methods used internally by the directive. Should not be called directly from user code.
   */

  tagsInput.factory('tiUtil', ["$timeout", function ($timeout) {
    var self = {};

    self.debounce = function (fn, delay) {
      var timeoutId;
      return function () {
        var args = arguments;
        $timeout.cancel(timeoutId);
        timeoutId = $timeout(function () {
          fn.apply(null, args);
        }, delay);
      };
    };

    self.makeObjectArray = function (array, key) {
      array = array || [];

      if (array.length > 0 && !angular.isObject(array[0])) {
        array.forEach(function (item, index) {
          array[index] = {};
          array[index][key] = item;
        });
      }

      return array;
    };

    self.findInObjectArray = function (array, obj, key, comparer) {
      var item = null;
      comparer = comparer || self.defaultComparer;
      array.some(function (element) {
        if (comparer(element[key], obj[key])) {
          item = element;
          return true;
        }
      });
      return item;
    };

    self.defaultComparer = function (a, b) {
      // I'm aware of the internationalization issues regarding toLowerCase()
      // but I couldn't come up with a better solution right now
      return self.safeToString(a).toLowerCase() === self.safeToString(b).toLowerCase();
    };

    self.safeHighlight = function (str, value) {
      if (!value) {
        return str;
      }

      function escapeRegexChars(str) {
        return str.replace(/([.?*+^$[\]\\(){}|-])/g, '\\$1');
      }

      str = self.encodeHTML(str);
      value = self.encodeHTML(value);
      var expression = new RegExp('&[^;]+;|' + escapeRegexChars(value), 'gi');
      return str.replace(expression, function (match) {
        return match.toLowerCase() === value.toLowerCase() ? '<em>' + match + '</em>' : match;
      });
    };

    self.safeToString = function (value) {
      return angular.isUndefined(value) || value == null ? '' : value.toString().trim();
    };

    self.encodeHTML = function (value) {
      return self.safeToString(value).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    };

    self.handleUndefinedResult = function (fn, valueIfUndefined) {
      return function () {
        var result = fn.apply(null, arguments);
        return angular.isUndefined(result) ? valueIfUndefined : result;
      };
    };

    self.replaceSpacesWithDashes = function (str) {
      return self.safeToString(str).replace(/\s/g, '-');
    };

    self.simplePubSub = function () {
      var events = {};
      return {
        on: function on(names, handler) {
          names.split(' ').forEach(function (name) {
            if (!events[name]) {
              events[name] = [];
            }

            events[name].push(handler);
          });
          return this;
        },
        trigger: function trigger(name, args) {
          var handlers = events[name] || [];
          handlers.every(function (handler) {
            return self.handleUndefinedResult(handler, true)(args);
          });
          return this;
        }
      };
    };

    return self;
  }]);
  /* HTML templates */

  tagsInput.run(["$templateCache", function ($templateCache) {
    $templateCache.put('ngTagsInput/tags-input.html', '<div class="host" tabindex="-1" data-ng-click="eventHandlers.host.click()" ti-transclude-append="">' + '<div class="tags" data-ng-class="{focused: hasFocus}">' + '<ul class="tag-list">' + '<li class="tag-item" data-ng-repeat="tag in tagList.items track by track(tag)" data-ng-class="{ selected: tag == tagList.selected }">' + '<ti-tag-item data="tag"></ti-tag-item>' + '</li>' + '</ul>' + '<input class="input u-no-margin--top u-no-margin--bottom" autocomplete="off" data-ng-model="newTag.text" data-ng-change="eventHandlers.input.change(newTag.text)" data-ng-keydown="eventHandlers.input.keydown($event)" data-ng-focus="eventHandlers.input.focus($event)" data-ng-blur="eventHandlers.input.blur($event)" data-ng-paste="eventHandlers.input.paste($event)" data-ng-trim="false" data-ng-class="{\'invalid-tag\': newTag.invalid}" data-ng-disabled="disabled" ti-bind-attrs="{type: options.type, placeholder: options.placeholder, tabindex: options.tabindex, spellcheck: options.spellcheck}" ti-autosize="">' + '</div>' + '</div>');
    $templateCache.put('ngTagsInput/tag-item.html', '<span ng-bind="$getDisplayText()"></span> ' + '<a class="p-icon--close" data-ng-click="$removeTag()" data-ng-bind="$$removeTagSymbol">' + 'Remove tag' + '</a>');
    $templateCache.put('ngTagsInput/auto-complete.html', '<div class="autocomplete" data-ng-if="suggestionList.visible">' + '<ul class="p-list suggestion-list">' + '<li class="suggestion-item create-tag-label" data-ng-if="getCurrentTag().length">' + '<span data-ng-click="addTag(getCurrentTag())">Create new tag</span> <span class="tag-item">{$ getCurrentTag() $}</span>' + '</li>' + '<li class="suggestion-item" data-ng-repeat="item in suggestionList.items track by track(item)" data-ng-class="{selected: item == suggestionList.selected}" data-ng-click="addSuggestionByIndex($index)" data-ng-mouseenter="suggestionList.select($index)">' + '<ti-autocomplete-match data="item"></ti-autocomplete-match>' + '</li>' + '</ul>' + '</div>' + '<div class="autocomplete no-suggestion" data-ng-if="!suggestionList.visible && hasFocus && shouldLoadSuggestions && getCurrentTag().length">' + '<ul class="p-list suggestion-list">' + '<li class="suggestion-item create-tag-label" data-ng-if="getCurrentTag().length">' + '<span data-ng-click="addTag(getCurrentTag())">Create new tag</span> <span class="tag-item">{$ getCurrentTag() $}</span>' + '</li>' + '</ul>' + '</div>');
    $templateCache.put('ngTagsInput/auto-complete-match.html', '<span data-ng-bind-html="$highlight($getDisplayText())"></span>');
  }]);
})();

/***/ }),

/***/ 199:
/***/ (function(module, exports, __webpack_require__) {

"use strict";


/*!
 * Angular Virtual Scroll Repeat v1.1.11
 * https://github.com/kamilkp/angular-vs-repeat/
 *
 * Copyright Kamil Pękala
 * http://github.com/kamilkp
 *
 * Released under the MIT License
 * https://opensource.org/licenses/MIT
 *
 * Date: 2018/03/09
 *
 */
(function (window, angular) {
  'use strict';
  /* jshint eqnull:true */

  /* jshint -W038 */
  // DESCRIPTION:
  // vsRepeat directive stands for Virtual Scroll Repeat. It turns a standard ngRepeated set of elements in a scrollable container
  // into a component, where the user thinks he has all the elements rendered and all he needs to do is scroll (without any kind of
  // pagination - which most users loath) and at the same time the browser isn't overloaded by that many elements/angular bindings etc.
  // The directive renders only so many elements that can fit into current container's clientHeight/clientWidth.
  // LIMITATIONS:
  // - current version only supports an Array as a right-hand-side object for ngRepeat
  // - all rendered elements must have the same height/width or the sizes of the elements must be known up front
  // USAGE:
  // In order to use the vsRepeat directive you need to place a vs-repeat attribute on a direct parent of an element with ng-repeat
  // example:
  // <div vs-repeat>
  //      <div ng-repeat="item in someArray">
  //          <!-- content -->
  //      </div>
  // </div>
  //
  // or:
  // <div vs-repeat>
  //      <div ng-repeat-start="item in someArray">
  //          <!-- content -->
  //      </div>
  //      <div>
  //         <!-- something in the middle -->
  //      </div>
  //      <div ng-repeat-end>
  //          <!-- content -->
  //      </div>
  // </div>
  //
  // You can also measure the single element's height/width (including all paddings and margins), and then speficy it as a value
  // of the attribute 'vs-repeat'. This can be used if one wants to override the automatically computed element size.
  // example:
  // <div vs-repeat="50"> <!-- the specified element height is 50px -->
  //      <div ng-repeat="item in someArray">
  //          <!-- content -->
  //      </div>
  // </div>
  //
  // IMPORTANT!
  //
  // - the vsRepeat directive must be applied to a direct parent of an element with ngRepeat
  // - the value of vsRepeat attribute is the single element's height/width measured in pixels. If none provided, the directive
  //      will compute it automatically
  // OPTIONAL PARAMETERS (attributes):
  // vs-repeat-container="selector" - selector for element containing ng-repeat. (defaults to the current element)
  // vs-scroll-parent="selector" - selector to the scrollable container. The directive will look for a closest parent matching
  //                              the given selector (defaults to the current element)
  // vs-horizontal - stack repeated elements horizontally instead of vertically
  // vs-offset-before="value" - top/left offset in pixels (defaults to 0)
  // vs-offset-after="value" - bottom/right offset in pixels (defaults to 0)
  // vs-excess="value" - an integer number representing the number of elements to be rendered outside of the current container's viewport
  //                      (defaults to 2)
  // vs-size - a property name of the items in collection that is a number denoting the element size (in pixels)
  // vs-autoresize - use this attribute without vs-size and without specifying element's size. The automatically computed element style will
  //              readjust upon window resize if the size is dependable on the viewport size
  // vs-scrolled-to-end="callback" - callback will be called when the last item of the list is rendered
  // vs-scrolled-to-end-offset="integer" - set this number to trigger the scrolledToEnd callback n items before the last gets rendered
  // vs-scrolled-to-beginning="callback" - callback will be called when the first item of the list is rendered
  // vs-scrolled-to-beginning-offset="integer" - set this number to trigger the scrolledToBeginning callback n items before the first gets rendered
  // EVENTS:
  // - 'vsRepeatTrigger' - an event the directive listens for to manually trigger reinitialization
  // - 'vsRepeatReinitialized' - an event the directive emits upon reinitialization done

  var dde = document.documentElement,
      matchingFunction = dde.matches ? 'matches' : dde.matchesSelector ? 'matchesSelector' : dde.webkitMatches ? 'webkitMatches' : dde.webkitMatchesSelector ? 'webkitMatchesSelector' : dde.msMatches ? 'msMatches' : dde.msMatchesSelector ? 'msMatchesSelector' : dde.mozMatches ? 'mozMatches' : dde.mozMatchesSelector ? 'mozMatchesSelector' : null;

  var closestElement = angular.element.prototype.closest || function (selector) {
    var el = this[0].parentNode;

    while (el !== document.documentElement && el != null && !el[matchingFunction](selector)) {
      el = el.parentNode;
    }

    if (el && el[matchingFunction](selector)) {
      return angular.element(el);
    } else {
      return angular.element();
    }
  };

  function getWindowScroll() {
    if ('pageYOffset' in window) {
      return {
        scrollTop: pageYOffset,
        scrollLeft: pageXOffset
      };
    } else {
      var sx,
          sy,
          d = document,
          r = d.documentElement,
          b = d.body;
      sx = r.scrollLeft || b.scrollLeft || 0;
      sy = r.scrollTop || b.scrollTop || 0;
      return {
        scrollTop: sy,
        scrollLeft: sx
      };
    }
  }

  function getClientSize(element, sizeProp) {
    if (element === window) {
      return sizeProp === 'clientWidth' ? window.innerWidth : window.innerHeight;
    } else {
      return element[sizeProp];
    }
  }

  function getScrollPos(element, scrollProp) {
    return element === window ? getWindowScroll()[scrollProp] : element[scrollProp];
  }

  function getScrollOffset(vsElement, scrollElement, isHorizontal) {
    var vsPos = vsElement.getBoundingClientRect()[isHorizontal ? 'left' : 'top'];
    var scrollPos = scrollElement === window ? 0 : scrollElement.getBoundingClientRect()[isHorizontal ? 'left' : 'top'];
    var correction = vsPos - scrollPos + (scrollElement === window ? getWindowScroll() : scrollElement)[isHorizontal ? 'scrollLeft' : 'scrollTop'];
    return correction;
  }

  var vsRepeatModule = angular.module('vs-repeat', []).directive('vsRepeat', ['$compile', '$parse', function ($compile, $parse) {
    return {
      restrict: 'A',
      scope: true,
      compile: function compile($element, $attrs) {
        var repeatContainer = angular.isDefined($attrs.vsRepeatContainer) ? angular.element($element[0].querySelector($attrs.vsRepeatContainer)) : $element,
            ngRepeatChild = repeatContainer.children().eq(0),
            ngRepeatExpression,
            childCloneHtml = ngRepeatChild[0].outerHTML,
            expressionMatches,
            lhs,
            rhs,
            rhsSuffix,
            originalNgRepeatAttr,
            collectionName = '$vs_collection',
            isNgRepeatStart = false,
            attributesDictionary = {
          'vsRepeat': 'elementSize',
          'vsOffsetBefore': 'offsetBefore',
          'vsOffsetAfter': 'offsetAfter',
          'vsScrolledToEndOffset': 'scrolledToEndOffset',
          'vsScrolledToBeginningOffset': 'scrolledToBeginningOffset',
          'vsExcess': 'excess',
          'vsScrollMargin': 'scrollMargin'
        };

        if (ngRepeatChild.attr('ng-repeat')) {
          originalNgRepeatAttr = 'ng-repeat';
          ngRepeatExpression = ngRepeatChild.attr('ng-repeat');
        } else if (ngRepeatChild.attr('data-ng-repeat')) {
          originalNgRepeatAttr = 'data-ng-repeat';
          ngRepeatExpression = ngRepeatChild.attr('data-ng-repeat');
        } else if (ngRepeatChild.attr('ng-repeat-start')) {
          isNgRepeatStart = true;
          originalNgRepeatAttr = 'ng-repeat-start';
          ngRepeatExpression = ngRepeatChild.attr('ng-repeat-start');
        } else if (ngRepeatChild.attr('data-ng-repeat-start')) {
          isNgRepeatStart = true;
          originalNgRepeatAttr = 'data-ng-repeat-start';
          ngRepeatExpression = ngRepeatChild.attr('data-ng-repeat-start');
        } else {
          throw new Error('angular-vs-repeat: no ng-repeat directive on a child element');
        }

        expressionMatches = /^\s*(\S+)\s+in\s+([\S\s]+?)(track\s+by\s+\S+)?$/.exec(ngRepeatExpression);
        lhs = expressionMatches[1];
        rhs = expressionMatches[2];
        rhsSuffix = expressionMatches[3];

        if (isNgRepeatStart) {
          var index = 0;
          var repeaterElement = repeatContainer.children().eq(0);

          while (repeaterElement.attr('ng-repeat-end') == null && repeaterElement.attr('data-ng-repeat-end') == null) {
            index++;
            repeaterElement = repeatContainer.children().eq(index);
            childCloneHtml += repeaterElement[0].outerHTML;
          }
        }

        repeatContainer.empty();
        return {
          pre: function pre($scope, $element, $attrs) {
            var repeatContainer = angular.isDefined($attrs.vsRepeatContainer) ? angular.element($element[0].querySelector($attrs.vsRepeatContainer)) : $element,
                childClone = angular.element(childCloneHtml),
                childTagName = childClone[0].tagName.toLowerCase(),
                originalCollection = [],
                originalLength,
                $$horizontal = typeof $attrs.vsHorizontal !== 'undefined',
                $beforeContent = angular.element('<' + childTagName + ' class="vs-repeat-before-content"></' + childTagName + '>'),
                $afterContent = angular.element('<' + childTagName + ' class="vs-repeat-after-content"></' + childTagName + '>'),
                autoSize = !$attrs.vsRepeat,
                sizesPropertyExists = !!$attrs.vsSize || !!$attrs.vsSizeProperty,
                $scrollParent = $attrs.vsScrollParent ? $attrs.vsScrollParent === 'window' ? angular.element(window) : closestElement.call(repeatContainer, $attrs.vsScrollParent) : repeatContainer,
                $$options = 'vsOptions' in $attrs ? $scope.$eval($attrs.vsOptions) : {},
                clientSize = $$horizontal ? 'clientWidth' : 'clientHeight',
                offsetSize = $$horizontal ? 'offsetWidth' : 'offsetHeight',
                scrollPos = $$horizontal ? 'scrollLeft' : 'scrollTop';
            $scope.totalSize = 0;

            if (!('vsSize' in $attrs) && 'vsSizeProperty' in $attrs) {
              console.warn('vs-size-property attribute is deprecated. Please use vs-size attribute which also accepts angular expressions.');
            }

            if ($scrollParent.length === 0) {
              throw 'Specified scroll parent selector did not match any element';
            }

            $scope.$scrollParent = $scrollParent;

            if (sizesPropertyExists) {
              $scope.sizesCumulative = [];
            } //initial defaults


            $scope.elementSize = +$attrs.vsRepeat || getClientSize($scrollParent[0], clientSize) || 50;
            $scope.offsetBefore = 0;
            $scope.offsetAfter = 0;
            $scope.scrollMargin = 0;
            $scope.excess = 2;

            if ($$horizontal) {
              $beforeContent.css('height', '100%');
              $afterContent.css('height', '100%');
            } else {
              $beforeContent.css('width', '100%');
              $afterContent.css('width', '100%');
            }

            Object.keys(attributesDictionary).forEach(function (key) {
              if ($attrs[key]) {
                $attrs.$observe(key, function (value) {
                  // '+' serves for getting a number from the string as the attributes are always strings
                  $scope[attributesDictionary[key]] = +value;
                  reinitialize();
                });
              }
            });
            $scope.$watchCollection(rhs, function (coll) {
              originalCollection = coll || [];
              refresh();
            });

            function refresh() {
              if (!originalCollection || originalCollection.length < 1) {
                $scope[collectionName] = [];
                originalLength = 0;
                $scope.sizesCumulative = [0];
              } else {
                originalLength = originalCollection.length;

                if (sizesPropertyExists) {
                  $scope.sizes = originalCollection.map(function (item) {
                    var s = $scope.$new(false);
                    angular.extend(s, item);
                    s[lhs] = item;
                    var size = $attrs.vsSize || $attrs.vsSizeProperty ? s.$eval($attrs.vsSize || $attrs.vsSizeProperty) : $scope.elementSize;
                    s.$destroy();
                    return size;
                  });
                  var sum = 0;
                  $scope.sizesCumulative = $scope.sizes.map(function (size) {
                    var res = sum;
                    sum += size;
                    return res;
                  });
                  $scope.sizesCumulative.push(sum);
                } else {
                  setAutoSize();
                }
              }

              reinitialize();
            }

            function setAutoSize() {
              if (autoSize) {
                $scope.$$postDigest(function () {
                  if (repeatContainer[0].offsetHeight || repeatContainer[0].offsetWidth) {
                    // element is visible
                    var children = repeatContainer.children(),
                        i = 0,
                        gotSomething = false,
                        insideStartEndSequence = false;

                    while (i < children.length) {
                      if (children[i].attributes[originalNgRepeatAttr] != null || insideStartEndSequence) {
                        if (!gotSomething) {
                          $scope.elementSize = 0;
                        }

                        gotSomething = true;

                        if (children[i][offsetSize]) {
                          $scope.elementSize += children[i][offsetSize];
                        }

                        if (isNgRepeatStart) {
                          if (children[i].attributes['ng-repeat-end'] != null || children[i].attributes['data-ng-repeat-end'] != null) {
                            break;
                          } else {
                            insideStartEndSequence = true;
                          }
                        } else {
                          break;
                        }
                      }

                      i++;
                    }

                    if (gotSomething) {
                      reinitialize();
                      autoSize = false;

                      if ($scope.$root && !$scope.$root.$$phase) {
                        $scope.$apply();
                      }
                    }
                  } else {
                    var dereg = $scope.$watch(function () {
                      if (repeatContainer[0].offsetHeight || repeatContainer[0].offsetWidth) {
                        dereg();
                        setAutoSize();
                      }
                    });
                  }
                });
              }
            }

            function getLayoutProp() {
              var layoutPropPrefix = childTagName === 'tr' ? '' : 'min-';
              var layoutProp = $$horizontal ? layoutPropPrefix + 'width' : layoutPropPrefix + 'height';
              return layoutProp;
            }

            childClone.eq(0).attr(originalNgRepeatAttr, lhs + ' in ' + collectionName + (rhsSuffix ? ' ' + rhsSuffix : ''));
            childClone.addClass('vs-repeat-repeated-element');
            repeatContainer.append($beforeContent);
            repeatContainer.append(childClone);
            $compile(childClone)($scope);
            repeatContainer.append($afterContent);
            $scope.startIndex = 0;
            $scope.endIndex = 0;

            function scrollHandler() {
              if (updateInnerCollection()) {
                $scope.$digest();
                var expectedSize = sizesPropertyExists ? $scope.sizesCumulative[originalLength] : $scope.elementSize * originalLength;

                if (expectedSize !== $element[0].clientHeight) {
                  console.warn('vsRepeat: size mismatch. Expected size ' + expectedSize + 'px whereas actual size is ' + $element[0].clientHeight + 'px. Fix vsSize on element:', $element[0]);
                }
              }
            }

            $scrollParent.on('scroll', scrollHandler);

            function onWindowResize() {
              if (typeof $attrs.vsAutoresize !== 'undefined') {
                autoSize = true;
                setAutoSize();

                if ($scope.$root && !$scope.$root.$$phase) {
                  $scope.$apply();
                }
              }

              if (updateInnerCollection()) {
                $scope.$apply();
              }
            }

            angular.element(window).on('resize', onWindowResize);
            $scope.$on('$destroy', function () {
              angular.element(window).off('resize', onWindowResize);
              $scrollParent.off('scroll', scrollHandler);
            });
            $scope.$on('vsRepeatTrigger', refresh);
            $scope.$on('vsRepeatResize', function () {
              autoSize = true;
              setAutoSize();
            });

            var _prevStartIndex, _prevEndIndex, _minStartIndex, _maxEndIndex;

            $scope.$on('vsRenderAll', function () {
              //e , quantum) {
              if ($$options.latch) {
                setTimeout(function () {
                  // var __endIndex = Math.min($scope.endIndex + (quantum || 1), originalLength);
                  var __endIndex = originalLength;
                  _maxEndIndex = Math.max(__endIndex, _maxEndIndex);
                  $scope.endIndex = $$options.latch ? _maxEndIndex : __endIndex;
                  $scope[collectionName] = originalCollection.slice($scope.startIndex, $scope.endIndex);
                  _prevEndIndex = $scope.endIndex;
                  $scope.$$postDigest(function () {
                    $beforeContent.css(getLayoutProp(), 0);
                    $afterContent.css(getLayoutProp(), 0);
                  });
                  $scope.$apply(function () {
                    $scope.$emit('vsRenderAllDone');
                  });
                });
              }
            });

            function reinitialize() {
              _prevStartIndex = void 0;
              _prevEndIndex = void 0;
              _minStartIndex = originalLength;
              _maxEndIndex = 0;
              updateTotalSize(sizesPropertyExists ? $scope.sizesCumulative[originalLength] : $scope.elementSize * originalLength);
              updateInnerCollection();
              $scope.$emit('vsRepeatReinitialized', $scope.startIndex, $scope.endIndex);
            }

            function updateTotalSize(size) {
              $scope.totalSize = $scope.offsetBefore + size + $scope.offsetAfter;
            }

            var _prevClientSize;

            function reinitOnClientHeightChange() {
              var ch = getClientSize($scrollParent[0], clientSize);

              if (ch !== _prevClientSize) {
                reinitialize();

                if ($scope.$root && !$scope.$root.$$phase) {
                  $scope.$apply();
                }
              }

              _prevClientSize = ch;
            }

            $scope.$watch(function () {
              if (typeof window.requestAnimationFrame === 'function') {
                window.requestAnimationFrame(reinitOnClientHeightChange);
              } else {
                reinitOnClientHeightChange();
              }
            });

            function updateInnerCollection() {
              var $scrollPosition = getScrollPos($scrollParent[0], scrollPos);
              var $clientSize = getClientSize($scrollParent[0], clientSize);
              var scrollOffset = repeatContainer[0] === $scrollParent[0] ? 0 : getScrollOffset(repeatContainer[0], $scrollParent[0], $$horizontal);
              var __startIndex = $scope.startIndex;
              var __endIndex = $scope.endIndex;

              if (sizesPropertyExists) {
                __startIndex = 0;

                while ($scope.sizesCumulative[__startIndex] < $scrollPosition - $scope.offsetBefore - scrollOffset - $scope.scrollMargin) {
                  __startIndex++;
                }

                if (__startIndex > 0) {
                  __startIndex--;
                } // Adjust the start index according to the excess


                __startIndex = Math.max(Math.floor(__startIndex - $scope.excess / 2), 0);
                __endIndex = __startIndex;

                while ($scope.sizesCumulative[__endIndex] < $scrollPosition - $scope.offsetBefore - scrollOffset + $scope.scrollMargin + $clientSize) {
                  __endIndex++;
                } // Adjust the end index according to the excess


                __endIndex = Math.min(Math.ceil(__endIndex + $scope.excess / 2), originalLength);
              } else {
                __startIndex = Math.max(Math.floor(($scrollPosition - $scope.offsetBefore - scrollOffset) / $scope.elementSize) - $scope.excess / 2, 0);
                __endIndex = Math.min(__startIndex + Math.ceil($clientSize / $scope.elementSize) + $scope.excess, originalLength);
              }

              _minStartIndex = Math.min(__startIndex, _minStartIndex);
              _maxEndIndex = Math.max(__endIndex, _maxEndIndex);
              $scope.startIndex = $$options.latch ? _minStartIndex : __startIndex;
              $scope.endIndex = $$options.latch ? _maxEndIndex : __endIndex; // Move to the end of the collection if we are now past it

              if (_maxEndIndex < $scope.startIndex) $scope.startIndex = _maxEndIndex;
              var digestRequired = false;

              if (_prevStartIndex == null) {
                digestRequired = true;
              } else if (_prevEndIndex == null) {
                digestRequired = true;
              }

              if (!digestRequired) {
                if ($$options.hunked) {
                  if (Math.abs($scope.startIndex - _prevStartIndex) >= $scope.excess / 2 || $scope.startIndex === 0 && _prevStartIndex !== 0) {
                    digestRequired = true;
                  } else if (Math.abs($scope.endIndex - _prevEndIndex) >= $scope.excess / 2 || $scope.endIndex === originalLength && _prevEndIndex !== originalLength) {
                    digestRequired = true;
                  }
                } else {
                  digestRequired = $scope.startIndex !== _prevStartIndex || $scope.endIndex !== _prevEndIndex;
                }
              }

              if (digestRequired) {
                $scope[collectionName] = originalCollection.slice($scope.startIndex, $scope.endIndex); // Emit the event

                $scope.$emit('vsRepeatInnerCollectionUpdated', $scope.startIndex, $scope.endIndex, _prevStartIndex, _prevEndIndex);
                var triggerIndex;

                if ($attrs.vsScrolledToEnd) {
                  triggerIndex = originalCollection.length - ($scope.scrolledToEndOffset || 0);

                  if ($scope.endIndex >= triggerIndex && _prevEndIndex < triggerIndex || originalCollection.length && $scope.endIndex === originalCollection.length) {
                    $scope.$eval($attrs.vsScrolledToEnd);
                  }
                }

                if ($attrs.vsScrolledToBeginning) {
                  triggerIndex = $scope.scrolledToBeginningOffset || 0;

                  if ($scope.startIndex <= triggerIndex && _prevStartIndex > $scope.startIndex) {
                    $scope.$eval($attrs.vsScrolledToBeginning);
                  }
                }

                _prevStartIndex = $scope.startIndex;
                _prevEndIndex = $scope.endIndex;
                var offsetCalculationString = sizesPropertyExists ? '(sizesCumulative[$index + startIndex] + offsetBefore)' : '(($index + startIndex) * elementSize + offsetBefore)';
                var parsed = $parse(offsetCalculationString);
                var o1 = parsed($scope, {
                  $index: 0
                });
                var o2 = parsed($scope, {
                  $index: $scope[collectionName].length
                });
                var total = $scope.totalSize;
                $beforeContent.css(getLayoutProp(), o1 + 'px');
                $afterContent.css(getLayoutProp(), total - o2 + 'px');
              }

              return digestRequired;
            }
          }
        };
      }
    };
  }]);

  if ( true && module.exports) {
    module.exports = vsRepeatModule.name;
  }
})(window, window.angular);

/***/ })

/******/ });
//# sourceMappingURL=vendor-min.js.map