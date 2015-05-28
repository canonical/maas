/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * MAAS Tag Manager
 *
 * Manages all of the tags in the browser. The manager uses the
 * RegionConnection to load the tags, update the tags, and listen for
 * notification events about tags.
 */

angular.module('MAAS').factory(
    'TagsManager',
    ['$q', '$rootScope', 'RegionConnection', 'Manager', function(
            $q, $rootScope, RegionConnection, Manager) {

        function TagsManager() {
            Manager.call(this);

            this._pk = "id";
            this._handler = "tag";

            // Listen for notify events for the tag object.
            var self = this;
            RegionConnection.registerNotifier("tag",
                function(action, data) {
                    self.onNotify(action, data);
                });
        }

        TagsManager.prototype = new Manager();

        // Helper for autocomplete that will return a string of tags that
        // contain the query text.
        TagsManager.prototype.autocomplete = function(query) {
            var matching = [];
            angular.forEach(this._items, function(item) {
                if(item.name.indexOf(query) > -1) {
                    matching.push(item.name);
                }
            });
            return matching;
        };

        return new TagsManager();
    }]);
