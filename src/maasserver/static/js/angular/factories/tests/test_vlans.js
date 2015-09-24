/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for VLANsManager.
 */


describe("VLANsManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the VLANsManager.
    var VLANsManager, SubnetsManager;
    beforeEach(inject(function($injector) {
        VLANsManager = $injector.get("VLANsManager");
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
        expect(VLANsManager._pk).toBe("id");
        expect(VLANsManager._handler).toBe("vlan");
    });

    describe("getSubnets", function() {

        it("returns subnet objects", function() {
            var i, subnets = [], vlan_subnets = [];
            for(i = 0; i < 6; i++) {
                var subnet = makeSubnet();
                subnets.push(subnet);
                if(i < 3) {
                    vlan_subnets.push(subnet);
                }
            }

            var subnet_ids = [];
            angular.forEach(vlan_subnets, function(subnet) {
                subnet_ids.push(subnet.id);
            });

            SubnetsManager._items = subnets;
            var vlan = {
                "subnet_ids": subnet_ids
            };
            expect(vlan_subnets).toEqual(VLANsManager.getSubnets(vlan));
        });
    });
});
