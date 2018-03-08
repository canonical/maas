/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * IO module.
 *
 */

YUI.add('maas.io', function(Y) {

Y.log('loading maas.io');

var module = Y.namespace('maas.io');

/**
 * Return a Y.IO object to talk to the MAAS website.
 *
 * @method getIO
 */
module.getIO = function() {
    var io = new Y.IO();
    // Populate the header used by Django for CSRF protection.
    Y.io.header('X-CSRFTOKEN', Y.Cookie.get("csrftoken"));
    return io;
};

}, '0.1', {'requires': ['cookie', 'io-base']}
);
