/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * TODO: document me.
 *
 * @module Y.mass.sample
 */

YUI.add('maas.sample', function(Y) {

Y.log('loading mass.sample');
var module = Y.namespace('maas.sample');

// Only used to mockup io in tests.
module._io = Y;


}, '0.1', {'requires': ['view', 'io', 'maas.node' ]}
);
