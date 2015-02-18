/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Nodes Filter
 */

angular.module('MAAS').filter('nodesFilter', ['$filter', 'SearchService',
    function($filter, SearchService) {

        // Default filter built-in angular. Used on all extra filters that do
        // not specify a specific type.
        var standardFilter = $filter('filter');

        // Helpers that convert the pseudo field on node to an actual
        // value from the node.
        var mappings = {
            cpu: function(node) {
                return node.cpu_count;
            },
            cores: function(node) {
                return node.cpu_count;
            },
            ram: function(node) {
                return node.memory;
            },
            mac: function(node) {
                macs = [];
                macs.push(node.pxe_mac);
                macs.push.apply(macs, node.extra_macs);
                return macs;
            },
            zone: function(node) {
                return node.zone.name;
            },
            power: function(node) {
                return node.power_state;
            }
        };

        // Return true when value is an integer.
        function isInteger(value) {
            // +1 done to silence js-lint.
            return value % +1 === 0;
        }

        // Return true when lowercase value contains the already
        // lowercased lowerTerm.
        function _matches(value, lowerTerm) {
            if(angular.isNumber(value)) {
                if(isInteger(value)) {
                    return value >= parseInt(lowerTerm, 10);
                } else {
                    return value >= parseFloat(lowerTerm);
                }
            } else if(angular.isString(value)) {
                return value.toLowerCase().indexOf(lowerTerm) >= 0;
            } else {
                return value === lowerTerm;
            }
        }

        // Return true if value matches lowerTerm, unless negate is true then
        // return false if matches.
        function matches(value, lowerTerm, negate) {
            var match = _matches(value, lowerTerm);
            if(negate) {
                return !match;
            }
            return match;
        }

        return function(nodes, search) {
            if(angular.isUndefined(nodes) ||
                angular.isUndefined(search) ||
                nodes.length === 0) {
                return nodes;
            }

            var filtered = nodes;
            var filters = SearchService.getCurrentFilters(search);
            angular.forEach(filters, function(terms, attr) {
                if(attr === '_') {
                    // Use the standard filter on terms that do not specify
                    // an attribute.
                    angular.forEach(terms, function(term) {
                        filtered = standardFilter(filtered, term);
                    });
                } else if(attr === 'in') {
                    // "in:" is used to filter the nodes by those that are
                    // currently selected.
                    angular.forEach(terms, function(term) {
                        var matched = [];
                        angular.forEach(filtered, function(node) {
                            if(node.$selected && term === "selected") {
                                matched.push(node);
                            } else if(!node.$selected && term === "!selected") {
                                matched.push(node);
                            }
                        });
                        filtered = matched;
                    });
                } else {
                    // Mapping function for the attribute.
                    var mapFunc = mappings[attr];

                    // Loop through each item and only select the matching.
                    var matched = [];
                    angular.forEach(filtered, function(node) {
                        var value;
                        if(angular.isFunction(mapFunc)) {
                            value = mapFunc(node);
                        } else if(node.hasOwnProperty(attr)) {
                            value = node[attr];
                        }

                        // Unable to get value for this node. So skip it.
                        if(angular.isUndefined(value)) {
                            return;
                        }

                        var i, j;
                        for(i = 0; i < terms.length; i++) {
                            var term = terms[i].toLowerCase();
                            var negate = false;

                            // '!' at the beginning means the term is negated.
                            if(term.indexOf('!') === 0) {
                                negate = true;
                                term = term.substring(1);
                            }

                            if(angular.isArray(value)) {
                                // Value is an array check if the term matches
                                // any value in the array.
                                for(j = 0; j < value.length; j++) {
                                    if(matches(value[j], term, negate)) {
                                        matched.push(node);
                                        return;
                                    }
                                }
                            } else {
                                // Standard value check that it matches the
                                // term.
                                if(matches(value, term, negate)) {
                                    matched.push(node);
                                    return;
                                }
                            }
                        }
                    });
                    filtered = matched;
                }
            });
            return filtered;
        };
    }]);
