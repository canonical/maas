/**
 * Merely loading this script into a page will cause it to look for a
 * single suite using the selector span#suite. If found, the text
 * within the span is considered to be a test module name. This is
 * then loaded, and its "suite" property is used to drive
 * Y.Test.Runner.
 *
 * Here's how to declare the suite to run:
 *
 *   <span id="suite">maas.something.test</span>
 *
 */
YUI().use("event", function(Y) {
    Y.on("domready", function() {
        var suite_node = Y.one("#suite");
        if (Y.Lang.isValue(suite_node)) {
            var suite_name = suite_node.get("text");
            Y.use(suite_name, "test", function(y) {
                var module = y, parts = suite_name.split(".");
                while (parts.length > 0) { module = module[parts.shift()]; }
                y.Test.Runner.add(module.suite);
                y.Test.Runner.run();
            });
        }
    });
});
