/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for SubnetsManager.
 */


describe("SubnetsManager", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load the SubnetsManager.
    var SubnetsManager;
    beforeEach(inject(function($injector) {
        SubnetsManager = $injector.get("SubnetsManager");
    }));

    it("set requires attributes", function() {
        expect(SubnetsManager._pk).toBe("id");
        expect(SubnetsManager._handler).toBe("subnet");
    });
});
