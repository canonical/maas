/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SpacesManager.
 */


describe("SpacesManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the SpacesManager.
    var SpacesManager, SubnetsManager;
    beforeEach(inject(function($injector) {
        SpacesManager = $injector.get("SpacesManager");
        SubnetsManager = $injector.get("SubnetsManager");
    }));

    // Make a fake subnet.
    function makeSubnet() {
        return {
            id: makeInteger(0, 5000),
            name: makeName("subnet")
        };
    }

    it("set requires attributes", function() {
        expect(SpacesManager._pk).toBe("id");
        expect(SpacesManager._handler).toBe("space");
    });

    describe("getSubnets", function() {

        it("returns subnet objects", function() {
            var i, subnets = [], space_subnets = [];
            for(i = 0; i < 6; i++) {
                var subnet = makeSubnet();
                subnets.push(subnet);
                if(i < 3) {
                    space_subnets.push(subnet);
                }
            }

            var subnet_ids = [];
            angular.forEach(space_subnets, function(subnet) {
                subnet_ids.push(subnet.id);
            });

            SubnetsManager._items = subnets;
            var space = {
                "subnet_ids": subnet_ids
            };
            expect(space_subnets).toEqual(SpacesManager.getSubnets(space));
        });
    });
});
