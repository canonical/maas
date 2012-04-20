/* Copyright 2012 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Widget to display the number of nodes in different states.
 *
 * @module Y.maas.nodes_chart
 */

YUI.add('maas.nodes_chart', function(Y) {

Y.log('loading maas.nodes_chart');

var module = Y.namespace('maas.nodes_chart');

var NodesChartWidget;

NodesChartWidget = function() {
    NodesChartWidget.superclass.constructor.apply(this, arguments);
};

NodesChartWidget.NAME = 'nodes-chart-widget';

var TRANSITION_TIME = 1000,
    TRANSITION_EASING = 'easeInOut',
    OUTER_COLOURS = ['#19b6ee', '#38b44a', '#0d80aa'],
    OFFLINE_COLOUR = '#dddddd',
    ADDED_COLOUR = '#ffffff',
    STROKE_WIDTH = 2,
    STROKE_COLOUR = '#ffffff',
    r;

NodesChartWidget.ATTRS = {
   /**
    * The node id to display the chart.
    *
    * @attribute node_id
    * @type string
    */
    node_id: {
        value: ''
    },
   /**
    * The width of the chart.
    *
    * @attribute width
    * @type integer
    */
    width: {
        value: 0
    },
   /**
    * The number of deployed nodes.
    *
    * @attribute deployed_nodes
    * @type integer
    */
    deployed_nodes: {
        value: 0
    },
   /**
    * The number of commissioned nodes.
    *
    * @attribute commissioned_nodes
    * @type integer
    */
    commissioned_nodes: {
        value: 0
    },
   /**
    * The number of queued nodes.
    *
    * @attribute queued_nodes
    * @type integer
    */
    queued_nodes: {
        value: 0
    },
   /**
    * The number of offline nodes.
    *
    * @attribute offline_nodes
    * @type integer
    */
    offline_nodes: {
        value: 0
    },
   /**
    * The number of added nodes.
    *
    * @attribute added_nodes
    * @type integer
    */
    added_nodes: {
        value: 0
    }
};

Y.extend(NodesChartWidget, Y.Widget, {
    /**
     * Create a circle element.
     *
     * @method _addCircle
     * @private
     * @return Circle
     */
     _addCircle: function(width, colour) {
        return r.add([{
            type: 'circle',
            cx: this._center().x,
            cy: this._center().y,
            r: width,
            fill: colour,
            stroke: STROKE_COLOUR,
            'stroke-width': STROKE_WIDTH
        }]);
    },

    /**
     * Get the radius of the chart.
     *
     * @method _radius
     * @private
     * @return integer
     */
     _radius: function() {
        return this.get('width')/2;
    },

    /**
     * Get the center coordinates.
     *
     * @method _center
     * @private
     * @return object
     */
     _center: function() {
        return {
            x: this._radius()+STROKE_WIDTH,
            y: this._radius()+STROKE_WIDTH
            };
    },

    /**
     * Update the chart.
     *
     * @method updateChart
     */
    updateChart: function() {
        var deployed_nodes = this.get('deployed_nodes');
        var commissioned_nodes = this.get('commissioned_nodes');
        var queued_nodes = this.get('queued_nodes');
        var offline_nodes = this.get('offline_nodes');
        var added_nodes = this.get('added_nodes');
        var outer_nodes = [
            {
                nodes: deployed_nodes,
                name: 'deployed_nodes',
                colour: OUTER_COLOURS[0],
                events: {
                    over: 'hover.deployed.over',
                    out: 'hover.deployed.out'
                    }
                },
            {
                nodes: commissioned_nodes,
                name: 'commissioned_nodes',
                colour: OUTER_COLOURS[2],
                events: {
                    over: 'hover.commissioned.over',
                    out: 'hover.commissioned.out'
                    }
                },
            {
                nodes: queued_nodes,
                name: 'queued_nodes',
                colour: OUTER_COLOURS[1],
                events: {
                    over: 'hover.queued.over',
                    out: 'hover.queued.out'
                    }
                }
            ];

        var outer_total = Y.Array.reduce(
            outer_nodes, 0, function(total, node) {
                return total + node.nodes; });
        var inner_total = offline_nodes + added_nodes;
        var total_nodes = outer_total + inner_total;
        if (outer_total > 0) {
            var create_outer = false;
            if (!this._outer_paths) {
                create_outer = true;
                this._outer_paths = [];
            }
            var segment_start = 0;
            Y.Array.each(outer_nodes, function(outer_node, i) {
                var segment_size = 360 / outer_total * outer_node.nodes;
                var segment = [
                    this._center().x,
                    this._center().y,
                    this._radius(),
                    segment_start,
                    segment_start + segment_size];
                if (create_outer) {
                    var slice = r.path();
                    slice.attr({
                        segment: segment,
                        fill: outer_node.colour,
                        stroke: STROKE_COLOUR,
                        'stroke-width': STROKE_WIDTH
                        });
                    Y.one(slice.node).on(
                        'hover',
                        function(e, over, out, name, widget) {
                            widget.fire(over, {nodes: widget.get(name)});
                        },
                        function(e, over, out, nodes, widget) {
                            widget.fire(out);
                        },
                        null,
                        outer_node.events.over,
                        outer_node.events.out,
                        outer_node.name,
                        this
                        );
                    this._outer_paths.push(slice);
                }
                else {
                    this._outer_paths[i].animate(
                        {segment: segment},
                        TRANSITION_TIME,
                        TRANSITION_EASING
                        );
                    this._outer_paths[i].angle =
                        segment_start - segment_size / 2;
                }
                segment_start += segment_size;
            }, this);
        }

        var offline_circle_width = 0;
        if (offline_nodes > 0) {
            offline_circle_width = inner_total / total_nodes * this._radius();
        }

        if (!this._offline_circle) {
            if (offline_nodes > 0) {
                this._offline_circle = this._addCircle(
                    offline_circle_width, OFFLINE_COLOUR);
                Y.one(this._offline_circle[0].node).on(
                    'hover',
                    function(e, widget) {
                        widget.fire(
                            'hover.offline.over',
                            {nodes: widget.get('offline_nodes')});
                    },
                    function(e, widget) {
                        widget.fire('hover.offline.out');
                    },
                    null,
                    this);
            }
        }
        else {
            this._offline_circle.toFront();
            this._offline_circle.animate(
                {r: offline_circle_width}, TRANSITION_TIME, TRANSITION_EASING);
        }

        var added_circle_width = 0;
        if (total_nodes === 0) {
            added_circle_width = this._radius() - STROKE_WIDTH * 2;
        }
        else if (added_nodes > 0) {
            added_circle_width = added_nodes / total_nodes * this._radius();
        }

        if (!this._added_circle) {
            this._added_circle = this._addCircle(
                added_circle_width, ADDED_COLOUR);
            Y.one(this._added_circle[0].node).on(
                'hover',
                function(e, widget) {
                    widget.fire(
                        'hover.added.over',
                        {nodes: widget.get('added_nodes')});
                },
                function(e, widget) {
                    widget.fire('hover.added.out');
                },
                null,
                this);
        }
        else {
            if (added_nodes !== total_nodes || total_nodes === 0) {
                this._added_circle.toFront();
                this._added_circle.animate(
                    {r: added_circle_width},
                    TRANSITION_TIME,
                    TRANSITION_EASING
                    );
            }
        }
    },

    initializer: function(cfg) {
        var canvas_size = this.get('width') + STROKE_WIDTH * 2;
        r = Raphael(this.get('node_id'), canvas_size, canvas_size);
        r.customAttributes.segment = function (x, y, r, a1, a2) {
            var flag = (a2 - a1) > 180;
            if (a1 === 0 && a2 === 360) {
                /* If the arc is a full circle we need to set the end
                   point to less than 360 degrees otherwise the start
                   and end points are calculated as the same
                   location. */
                a2 = 359.99;
            }
            a1 = (a1 % 360) * Math.PI / 180;
            a2 = (a2 % 360) * Math.PI / 180;
            return {
                path: [
                    ['M', x, y],
                    ['l', r * Math.cos(a1), r * Math.sin(a1)],
                    [
                        'A', r, r, 0, +flag, 1,
                        x + r * Math.cos(a2),
                        y + r * Math.sin(a2)],
                    ['z']
                ]
            };
        };
        r.add([{
            type: 'circle',
            cx: this._center().x,
            cy: this._center().y,
            r: this._radius() - STROKE_WIDTH,
            fill: '#ffffff',
            stroke: '#19b6ee',
            'stroke-width': 2,
            'stroke-dasharray': '- '
        }]);
        this.updateChart();
    }
});

module.NodesChartWidget = NodesChartWidget;

}, '0.1', {'requires': ['array-extras', 'event-custom', 'widget']}
);
