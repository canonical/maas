/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Nodes Search Services
 */

function SearchService() {
  // Holds an empty filter object.
  var emptyFilter = { _: [] };

  // Return a new empty filter;
  this.getEmptyFilter = function() {
    return angular.copy(emptyFilter);
  };

  // Splits the search string into different terms based on white space.
  // This handles the ability for whitespace to be inside of '(', ')'.
  //
  // XXX blake_r 28-01-15: This could be improved with a regex, but was
  // unable to come up with one that would allow me to validate the end
  // ')' in the string.
  this.getSplitSearch = function(search) {
    var terms = search.split(" ");
    var fixedTerms = [];
    var spanningParentheses = false;
    angular.forEach(terms, function(term) {
      if (spanningParentheses) {
        // Previous term had an opening '(' but not a ')'. This
        // term should join that previous term.
        fixedTerms[fixedTerms.length - 1] += " " + term;

        // If the term contains the ending ')' then its the last
        // in the group.
        if (term.indexOf(")") !== -1) {
          spanningParentheses = false;
        }
      } else {
        // Term is not part of a previous '(' span.
        fixedTerms.push(term);

        var startIdx = term.indexOf("(");
        if (startIdx !== -1) {
          if (term.indexOf(")", startIdx) === -1) {
            // Contains a starting '(' but not a ending ')'.
            spanningParentheses = true;
          }
        }
      }
    });

    if (spanningParentheses) {
      // Missing ending parentheses so error with terms.
      return null;
    }
    return fixedTerms;
  };

  // Return all of the currently active filters for the given search.
  this.getCurrentFilters = function(search) {
    var filters = this.getEmptyFilter();
    if (search.length === 0) {
      return filters;
    }
    var searchTerms = this.getSplitSearch(search);
    if (!searchTerms) {
      return null;
    }
    angular.forEach(searchTerms, function(terms) {
      terms = terms.split(":");
      if (terms.length === 1) {
        // Search term is not specifying a specific field. Gets
        // add to the '_' section of the filters.
        if (filters._.indexOf(terms[0]) === -1) {
          filters._.push(terms[0]);
        }
      } else {
        var field = terms.shift();
        var values = terms.join(":");

        // Remove the starting '(' and ending ')'.
        values = values.replace("(", "");
        values = values.replace(")", "");

        // If empty values then do nothing.
        if (values.length === 0) {
          return;
        }

        // Split the values based on comma.
        values = values.split(",");

        // Add the values to filters.
        if (angular.isUndefined(filters[field])) {
          filters[field] = [];
        }
        angular.forEach(values, function(value) {
          if (filters[field].indexOf(value) === -1) {
            filters[field].push(value);
          }
        });
      }
    });
    return filters;
  };

  // Convert "filters" into a search string.
  this.filtersToString = function(filters) {
    var search = "";
    angular.forEach(filters, function(terms, type) {
      // Skip empty and skip "_" as it gets appended at the
      // beginning of the search.
      if (terms.length === 0 || type === "_") {
        return;
      }
      search += type + ":(" + terms.join(",") + ") ";
    });
    if (filters._.length > 0) {
      search = filters._.join(" ") + " " + search;
    }
    return search.trim();
  };

  // Return the index of the value in the type for the filter.
  this._getFilterValueIndex = function(filters, type, value) {
    var values = filters[type];
    if (angular.isUndefined(values)) {
      return -1;
    }
    var lowerValues = values.map(function(value) {
      return value.toLowerCase();
    });
    return lowerValues.indexOf(value.toLowerCase());
  };

  // Return true if the type and value are in the filters.
  this.isFilterActive = function(filters, type, value, exact) {
    var values = filters[type];
    if (angular.isUndefined(values)) {
      return false;
    }
    if (angular.isUndefined(exact)) {
      exact = false;
    }
    if (exact) {
      value = "=" + value;
    }
    return this._getFilterValueIndex(filters, type, value) !== -1;
  };

  // Toggles a filter on or off based on type and value.
  this.toggleFilter = function(filters, type, value, exact) {
    if (angular.isUndefined(filters[type])) {
      filters[type] = [];
    }
    if (exact) {
      value = "=" + value;
    }
    var idx = this._getFilterValueIndex(filters, type, value);
    if (idx === -1) {
      filters[type].push(value);
    } else {
      filters[type].splice(idx, 1);
    }
    return filters;
  };

  // Holds all stored filters.
  var storedFilters = {};

  // Store a filter for later.
  this.storeFilters = function(name, filters) {
    storedFilters[name] = filters;
  };

  // Retrieve a stored filter.
  this.retrieveFilters = function(name) {
    return storedFilters[name];
  };
}

export default SearchService;
