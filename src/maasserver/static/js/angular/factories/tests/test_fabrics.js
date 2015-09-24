/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for FabricsManager.
 */


describe("FabricsManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the FabricsManager.
    var FabricsManager, VLANsManager;
    beforeEach(inject(function($injector) {
        FabricsManager = $injector.get("FabricsManager");
        VLANsManager = $injector.get("VLANsManager");
    }));

    // Make a fake VLAN.
    function makeVLAN() {
        return {
            id: makeInteger(0, 5000),
            name: makeName("vlan")
        };
    }

    it("set requires attributes", function() {
        expect(FabricsManager._pk).toBe("id");
        expect(FabricsManager._handler).toBe("fabric");
    });

    describe("getVLANs", function() {

        it("returns VLAN objects", function() {
            var i, vlans = [], fabric_vlans = [];
            for(i = 0; i < 6; i++) {
                var vlan = makeVLAN();
                vlans.push(vlan);
                if(i < 3) {
                    fabric_vlans.push(vlan);
                }
            }

            var vlan_ids = [];
            angular.forEach(fabric_vlans, function(vlan) {
                vlan_ids.push(vlan.id);
            });

            VLANsManager._items = vlans;
            var fabric = {
                "vlan_ids": vlan_ids
            };
            expect(fabric_vlans).toEqual(FabricsManager.getVLANs(fabric));
        });
    });
});
