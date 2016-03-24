/* Copyright 2015-2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for FabricsManager.
 */


describe("FabricsManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the FabricsManager.
    var FabricsManager, VLANsManager, RegionConnection;
    beforeEach(inject(function($injector) {
        FabricsManager = $injector.get("FabricsManager");
        VLANsManager = $injector.get("VLANsManager");
        RegionConnection = $injector.get("RegionConnection");
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

    describe("getName", function() {

        it("returns undefined if no object is passed in", function() {
            expect(FabricsManager.getName()).toBe(undefined);
        });

        it("returns name if name exists", function() {
            var fabric = {
                name: "jury-rigged"
            };
            expect(FabricsManager.getName(fabric)).toBe('jury-rigged');
        });

        it("returns name if name is null", function() {
            var fabric = {
                id: makeInteger(0, 1000),
                name: null
            };
            expect(FabricsManager.getName(fabric)).toBe('fabric-' + fabric.id);
        });

    });

    describe("create", function() {

        it("calls the region with expected parameters", function() {
            var obj = {};
            var result = {};
            spyOn(RegionConnection, "callMethod").and.returnValue(result);
            expect(FabricsManager.create(obj)).toBe(result);
            expect(RegionConnection.callMethod).toHaveBeenCalledWith(
                "fabric.create", obj
            );
        });
    });
});
