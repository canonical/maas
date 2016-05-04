/* Copyright 2016 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for nodesFilter.
 */

describe("filterBySubnet", function() {

    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Load filterBySubnet function.
    var filterBySubnet;
    beforeEach(inject(function($filter) {
        filterBySubnet = $filter("filterBySubnet");
    }));

    it("returns an empty list for a null subnet", function() {
        expect(filterBySubnet([], null)).toEqual([]);
    });

    it("does not match unrelated object", function() {
        var subnet = {id: 1};
        var foreign_object = {subnet: 0};
        expect(filterBySubnet([foreign_object], subnet)).toEqual([]);
    });

    it("matches related object", function() {
        var subnet = {id: 1};
        var foreign_object = {subnet: 1};
        expect(
            filterBySubnet([foreign_object], subnet))
            .toEqual([foreign_object]);
    });

    it("matches related objects", function() {
        var subnet = {id: 1};
        var foreign1 = {subnet: 0};
        var foreign2 = {subnet: 1};
        expect(
            filterBySubnet([foreign1, foreign2], subnet))
            .toEqual([foreign2]);
    });

    it("matches related objects by id", function() {
        var subnet = {id: 1};
        var foreign1 = {subnet: 0};
        var foreign2 = {subnet: 1};
        expect(
            filterBySubnet([foreign1, foreign2], subnet.id))
            .toEqual([foreign2]);
    });

    it("matches multiple related objects", function() {
        var subnet = {id: 1};
        var foreign1 = {subnet: 1};
        var foreign2 = {subnet: 0};
        var foreign3 = {subnet: 1};
        expect(
            filterBySubnet([foreign1, foreign2, foreign3], subnet))
            .toEqual([foreign1, foreign3]);
    });
});
