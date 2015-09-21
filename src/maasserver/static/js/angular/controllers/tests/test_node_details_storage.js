/* Copyright 2015 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Unit tests for NodeStorageController.
 */

describe("NodeStorageController", function() {
    // Load the MAAS module.
    beforeEach(module("MAAS"));

    // Grab the needed angular pieces.
    var $controller, $rootScope, $parentScope, $scope, $q;
    beforeEach(inject(function($injector) {
        $controller = $injector.get("$controller");
        $rootScope = $injector.get("$rootScope");
        $parentScope = $rootScope.$new();
        $scope = $parentScope.$new();
        $q = $injector.get("$q");
    }));

    // Create the node and functions that will be called on the parent.
    var node, updateNodeSpy, canEditSpy;
    beforeEach(function() {
        node = {
            disks: []
        };
        updateNodeSpy = jasmine.createSpy("updateNode");
        canEditSpy = jasmine.createSpy("canEdit");
        $parentScope.node = node;
        $parentScope.updateNode = updateNodeSpy;
        $parentScope.canEdit = canEditSpy;
    });

    // Makes the NodeStorageController
    function makeController() {
        // Create the controller.
        var controller = $controller("NodeStorageController", {
            $scope: $scope
        });
        return controller;
    }

    it("sets initial values", function() {
        var controller = makeController();
        expect($scope.editing).toBe(false);
        expect($scope.column).toBe('model');
        expect($scope.disks).toEqual([]);
    });

    it("starts watching disks once nodeLoaded called", function() {
        var controller = makeController();

        spyOn($scope, "$watch");
        $scope.nodeLoaded();

        var watches = [];
        var i, calls = $scope.$watch.calls.allArgs();
        for(i = 0; i < calls.length; i++) {
            watches.push(calls[i][0]);
        }

        expect(watches).toEqual(["node.disks"]);
    });

    it("disks updated once nodeLoaded called", function() {
        var disks = [
            {
                id: 0,
                model: makeName("model"),
                tags: [makeName("tag")]
            },
            {
                id: 1,
                model: makeName("model"),
                tags: [makeName("tag")]
            }
        ];
        node.disks = disks;

        var withFixesTags = angular.copy(disks);
        angular.forEach(withFixesTags, function(disk) {
            var tags = [];
            angular.forEach(disk.tags, function(tag) {
                tags.push({ text: tag });
            });
            disk.tags = tags;
        });

        var controller = makeController();
        $scope.nodeLoaded();
        $rootScope.$digest();
        expect($scope.disks).toEqual(withFixesTags);
        expect($scope.disks).not.toBe(disks);
    });

    describe("edit", function() {

        it("doesnt sets editing to true if cannot edit", function() {
            var controller = makeController();
            canEditSpy.and.returnValue(false);
            $scope.editing = false;
            $scope.edit();
            expect($scope.editing).toBe(false);
        });

        it("sets editing to true", function() {
            var controller = makeController();
            canEditSpy.and.returnValue(true);
            $scope.editing = false;
            $scope.edit();
            expect($scope.editing).toBe(true);
        });
    });

    describe("cancel", function() {

        it("sets editing to false", function() {
            var controller = makeController();
            $scope.editing = true;
            $scope.cancel();
            expect($scope.editing).toBe(false);
        });

        it("calls updateDisks", function() {
            var controller = makeController();
            $scope.editing = true;

            // Updates physicalDisks so we can check that updateStorage
            // is called.
            node.disks = [
                {
                    id: 0,
                    model: makeName("model"),
                    tags: []
                }
            ];

            $scope.cancel();

            // Since updateStorage is private in the controller, check
            // that the disks are updated.
            expect($scope.disks).toEqual(node.disks);
        });
    });

    describe("save", function() {

        it("sets editing to false", function() {
            var controller = makeController();

            $scope.editing = true;
            $scope.save();

            expect($scope.editing).toBe(false);
        });

        it("calls updateNode with copy of node", function() {
            var controller = makeController();

            $scope.editing = true;
            $scope.save();

            var calledWithNode = updateNodeSpy.calls.argsFor(0)[0];
            expect(calledWithNode).not.toBe(node);
        });

        it("calls updateNode with new tags on disks", function() {
            var controller = makeController();
            var disks = [
                {
                    id: 0,
                    model: makeName("model"),
                    tags: [makeName("tag"), makeName("tag")]
                }
            ];
            var disksWithnewTags = angular.copy(disks);
            disksWithnewTags[0].tags = [makeName("tag"), makeName("tag")];

            node.disks = disks;
            $scope.editing = true;
            $scope.disks = disksWithnewTags;
            $scope.save();

            var calledWithNode = updateNodeSpy.calls.argsFor(0)[0];
            expect(calledWithNode.disks).toBe(disksWithnewTags);
            expect(calledWithNode.disks).not.toBe(
                disks);
        });
    });
});
