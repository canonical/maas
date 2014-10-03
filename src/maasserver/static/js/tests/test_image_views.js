/* Copyright 2014 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 */

YUI({ useBrowserConsole: true }).add('maas.image_views.tests', function(Y) {

Y.log('loading maas.image_views.tests');
var namespace = Y.namespace('maas.image_views.tests');

var module = Y.maas.image_views;
var suite = new Y.Test.Suite("maas.image_views Tests");

// Dump this HTML into #placeholder to get DOM hooks for the view.
var view_hooks = Y.one('#view-hooks').getContent();


suite.add(new Y.maas.testing.TestCase({
    name: 'test-image-views-ImageListLoader',

    exampleResponse: {
        region_import_running: true,
        cluster_import_running: false,
        resources: [
            {id: '3', name: 'ubuntu/trusty'},
            {id: '4', name: 'ubtunu/utopic'}
        ]
    },

    makeImageListLoader: function() {
        var view = new Y.maas.image_views.ImageListLoader();
        this.addCleanup(Y.bind(view.destroy, view));
        return view;
    },

    testInitialization: function() {
        var view = this.makeImageListLoader();
        Y.Assert.areEqual('imageList', view.modelList.name);
    },

    testRenderDoesNotCallLoad: function() {
        // The initial call to .render() does *not* trigger the loading
        // of the images.
        var self = this;

        var mockXhr = Y.Mock();
        Y.Mock.expect(mockXhr, {
            method: 'send',
            args: [MAAS_config.uris.images_handler, Y.Mock.Value.Any],
            run: function(uri, cfg) {
                var out = new Y.Base();
                out.response = Y.JSON.stringify(self.exampleResponse);
                cfg.on.success(Y.guid(), out);
            }
        });
        this.mockIO(mockXhr, module);

        var view = this.makeImageListLoader();

        view.render();
        // The model list has not been populated.
        Y.Assert.areEqual(0, view.modelList.size());
    },

    testAddLoader: function() {
        // A mock loader.
        var loader = new Y.Base();

        // Capture event registrations.
        var events = {};
        loader.on = function(event, callback) {
            events[event] = callback;
        };

        var view = this.makeImageListLoader();
        view.addLoader(loader);

        // Several events are registered.
        Y.Assert.areSame(view.loadImagesStarted, events["io:start"]);
        Y.Assert.areSame(view.loadImagesEnded, events["io:end"]);
        Y.Assert.areSame(view.loadImagesFailed, events["io:failure"]);
        Y.Assert.isFunction(events["io:success"]);
    },

    testLoadImages: function() {
        var response = Y.JSON.stringify(this.exampleResponse);
        var view = this.makeImageListLoader();
        view.loadImages(response);
        Y.Assert.isTrue(view.loaded);
        Y.Assert.areEqual(2, view.modelList.size());
        Y.Assert.isTrue(view.regionImportRunning);
        Y.Assert.isFalse(view.clusterImportRunning);
        Y.Assert.areEqual('ubtunu/utopic', view.modelList.item(0).get('name'));
        Y.Assert.areEqual('ubuntu/trusty', view.modelList.item(1).get('name'));
    },

    testLoadImages_invalid_data: function() {
        var response = "{garbled data}";
        var view = this.makeImageListLoader();

        var loadImagesFailedCalled = false;
        view.loadImagesFailed = function() {
            loadImagesFailedCalled = true;
        };

        view.loadImages(response);
        Y.Assert.isTrue(view.loaded);
        Y.Assert.areEqual(0, view.modelList.size());
        Y.Assert.isTrue(loadImagesFailedCalled);
    },

    testLoadImages_calls_render: function() {
        var response = Y.JSON.stringify(this.exampleResponse);
        var view = this.makeImageListLoader();

        var renderCalled = false;
        view.render = function() {
            renderCalled = true;
        };

        view.loadImages(response);
        Y.Assert.isTrue(renderCalled);
    },

    assertModelListMatchesImages: function(modelList, images) {
        Y.Assert.areEqual(images.length, modelList.size());
        Y.Array.each(images, function(image) {
            var model = modelList.getById(image.id);
            Y.Assert.isObject(model);
            Y.Assert.areEqual(image.name, model.get("name"));
            Y.Assert.areEqual(image.title, model.get("title"));
        });
    },

    test_mergeImages_when_modelList_is_empty: function() {
        var view = this.makeImageListLoader();
        var images = [
            {id: 1, name: "name1", title: "title1"},
            {id: 2, name: "name2", title: "title2"},
            {id: 3, name: "name3", title: "title2"}
        ];
        Y.Assert.areEqual(0, view.modelList.size());
        view.mergeImages(images);
        this.assertModelListMatchesImages(view.modelList, images);
    },

    test_mergeImages_when_modelList_is_not_empty: function() {
        var view = this.makeImageListLoader();
        var images_before = [
            {id: 1, name: "name1", title: "title1"},
            {id: 3, name: "name3", title: "title3"}
        ];
        var images_after = [
            {id: 1, name: "name1after", title: "title1after"},
            {id: 2, name: "name2after", title: "title2after"}
        ];
        view.mergeImages(images_before);
        this.assertModelListMatchesImages(view.modelList, images_before);
        view.mergeImages(images_after);
        this.assertModelListMatchesImages(view.modelList, images_after);
    }

}));

suite.add(new Y.maas.testing.TestCase({
    name: 'test-images-views-ImagesView',

    setUp : function () {
        Y.one('#placeholder').empty();
        this.regionImporting = true;
        this.clusterImporting = false;
        this.ubuntuImages = [
            {
                id: 1,
                rtype: Y.maas.enums.BOOT_RESOURCE_TYPE.SYNCED,
                name: 'ubuntu/trusty',
                title: '14.04 LTS',
                arch: 'amd64',
                size: '150 MB',
                complete: true,
                status: "Complete",
                downloading: false,
                numberOfNodes: 1,
                lastUpdate: '10/1/14',
            },
            {
                id: 2,
                rtype: Y.maas.enums.BOOT_RESOURCE_TYPE.SYNCED,
                name: 'ubuntu/precise',
                title: '12.04 LTS',
                arch: 'amd64',
                size: '125 MB',
                complete: true,
                status: "Complete",
                downloading: false,
                numberOfNodes: 0,
                lastUpdate: '10/1/14',
            },
            {
                id: 3,
                rtype: Y.maas.enums.BOOT_RESOURCE_TYPE.SYNCED,
                name: 'ubuntu/utopic',
                title: '14.10',
                arch: 'amd64',
                size: '155 MB',
                complete: false,
                status: "Downloading 13%",
                downloading: true,
                numberOfNodes: 0,
                lastUpdate: '10/1/14',
            },
        ];
    },

    /**
     * Counter to generate unique numbers.
     */
    counter: 0,

    /**
     * Get next value of this.counter, and increment.
     */
    getNumber: function() {
        return this.counter++;
    },

    /**
     * Create a images view, render it, and arrange for its cleanup.
     *
     * The "regionImporting" parameter defaults to this.regionImporting.
     * The "clusterImporting" parameter defaults to this.clusterImporting.
     * The "ubuntuImages" parameter defaults to this.ubuntuImages.
     */
    makeImagesView: function(regionImporting, clusterImporting, ubuntuImages) {
        if (regionImporting === undefined) {
            regionImporting = this.regionImporting;
        }
        if (clusterImporting === undefined) {
            clusterImporting = this.clusterImporting;
        }
        if (ubuntuImages === undefined) {
            ubuntuImages = this.ubuntuImages;
        }
        var root_node_id = 'widget-' + this.getNumber().toString();
        var new_view = Y.Node.create('<div />').set('id', root_node_id);
        this.addCleanup(function() { new_view.remove(); });
        new_view.append(Y.Node.create(view_hooks));
        Y.one('#placeholder').append(new_view);
        var view = create_images_view(
            regionImporting, clusterImporting, ubuntuImages,
            this, '#' + root_node_id);
        this.addCleanup(function() { view.destroy(); });
        return view;
    },

    testLoaderHiddenAndContentShown: function() {
        var view = this.makeImagesView();
        Y.Assert.isTrue(view.srcNode.one('#loader').hasClass('hidden'));
        Y.Assert.isFalse(view.srcNode.one('#content').hasClass('hidden'));
    },

    testLoaderShownAndContentHidden: function() {
        var view = this.makeImagesView();
        view.loaded = false;
        view.render();
        Y.Assert.isFalse(view.srcNode.one('#loader').hasClass('hidden'));
        Y.Assert.isTrue(view.srcNode.one('#content').hasClass('hidden'));
    },

    testImportingHidden: function() {
        var view = this.makeImagesView(false, false);
        Y.Assert.isTrue(view.srcNode.one('#importer').hasClass('hidden'));
        Y.Assert.areSame(
            '',
            view.srcNode.one('#importer').one('.importing-text').getContent());
    },

    testImportingRegion: function() {
        var view = this.makeImagesView(true, false);
        Y.Assert.isFalse(view.srcNode.one('#importer').hasClass('hidden'));
        Y.Assert.areSame(
            view.regionImportingText,
            view.srcNode.one('#importer').one('.importing-text').getContent());
    },

    testImportingCluster: function() {
        var view = this.makeImagesView(false, true);
        Y.Assert.isFalse(view.srcNode.one('#importer').hasClass('hidden'));
        Y.Assert.areSame(
            view.clusterImportingText,
            view.srcNode.one('#importer').one('.importing-text').getContent());
    },

    testHidesUbuntuOptionsWhenRegionImporting: function() {
        var view = this.makeImagesView(true);
        Y.Assert.isTrue(
            view.srcNode.one('#ubuntu-options').hasClass('hidden'));
    },

    testShowsUbuntuOptionsWhenRegionNotImporting: function() {
        var view = this.makeImagesView(false);
        Y.Assert.isFalse(
            view.srcNode.one('#ubuntu-options').hasClass('hidden'));
    },

    testHidesUbuntuButtonWhenRegionImporting: function() {
        var view = this.makeImagesView(true);
        Y.Assert.isTrue(
            view.srcNode.one('#ubuntu-apply').hasClass('hidden'));
    },

    testShowsUbuntuButtonWhenRegionNotImporting: function() {
        var view = this.makeImagesView(false);
        Y.Assert.isFalse(
            view.srcNode.one('#ubuntu-apply').hasClass('hidden'));
    },

    testShowsMissingIfEmptyImages: function() {
        var view = this.makeImagesView(false, false, []);
        Y.Assert.isFalse(
            view.srcNode.one('#missing-ubuntu-images').hasClass('hidden'));
        Y.Assert.isTrue(
            view.srcNode.one('#ubuntu-resources').hasClass('hidden'));
    },

    testShowsMissingIfEmptyUbuntuImages: function() {
        var none_ubuntu_images = [
            {
                id: 1,
                rtype: Y.maas.enums.BOOT_RESOURCE_TYPE.SYNCED,
                name: "centos/centos65",
            },
            {
                id: 2,
                rtype: Y.maas.enums.BOOT_RESOURCE_TYPE.SYNCED,
                name: "centos/centos70",
            }
        ];
        var view = this.makeImagesView(false, false, none_ubuntu_images);
        Y.Assert.isFalse(
            view.srcNode.one('#missing-ubuntu-images').hasClass('hidden'));
        Y.Assert.isTrue(
            view.srcNode.one('#ubuntu-resources').hasClass('hidden'));
    },

    testHidesMissingIfUbuntuImages: function() {
        var view = this.makeImagesView();
        Y.Assert.isTrue(
            view.srcNode.one('#missing-ubuntu-images').hasClass('hidden'));
        Y.Assert.isFalse(
            view.srcNode.one('#ubuntu-resources').hasClass('hidden'));
    },

    testRendersUbuntuTableData: function() {
        var view = this.makeImagesView();
        var tableBody = view.srcNode.one('#ubuntu-resources').one('tbody');
        var tableRows = tableBody.get('children');
        Y.each(view.getUbuntuImages(), function(image, i) {
            var row = tableRows.item(i);
            var columns = row.get('children');
            Y.Assert.areSame(image.get('title'), columns.item(1).getContent());
            Y.Assert.areSame(image.get('arch'), columns.item(2).getContent());
            Y.Assert.areSame(image.get('size'), columns.item(3).getContent());
            Y.Assert.areSame(
                image.get('numberOfNodes').toString(),
                columns.item(4).getContent());
            Y.Assert.areSame(
                image.get('lastUpdate'),
                columns.item(5).getContent());
        });
    },

    testUpdateUbuntuButtonSetValueForApply: function() {
        var view = this.makeImagesView();
        var ubuntuButton = view.srcNode.one('#ubuntu-apply');
        view.updateUbuntuButton(true);
        Y.Assert.areSame('Apply changes', ubuntuButton.get('value'));
    },

    testUpdateUbuntuButtonSetValueForImport: function() {
        var view = this.makeImagesView();
        var ubuntuButton = view.srcNode.one('#ubuntu-apply');
        view.updateUbuntuButton(false);
        Y.Assert.areSame('Import images', ubuntuButton.get('value'));
    },

    testUpdateUbuntuButtonDoesNothingIfLockValueExists: function() {
        var view = this.makeImagesView();
        var ubuntuButton = view.srcNode.one('#ubuntu-apply');
        ubuntuButton.set('value', 'testing');
        ubuntuButton.setData('lock-value', 'true');
        view.updateUbuntuButton(true);
        Y.Assert.areSame('testing', ubuntuButton.get('value'));
    },

    testGetSpinnerReturnsEmptyForComplete: function() {
        var view = this.makeImagesView();
        var model = new Y.maas.image.Image({complete: true});
        Y.Assert.areSame('', view.getSpinner(model));
    },

    testGetSpinnerReturnsStatusInTitle: function() {
        var view = this.makeImagesView();
        var model = new Y.maas.image.Image({status: 'Testing'});
        var html = view.getSpinner(model);
        var node = Y.Node.create(html);
        Y.Assert.areSame('Testing', node.get('title'));
    },

    testGetSpinnerHasSpinnerClass: function() {
        var view = this.makeImagesView();
        var model = new Y.maas.image.Image();
        var html = view.getSpinner(model);
        var node = Y.Node.create(html);
        Y.Assert.isTrue(node.hasClass('spinner'));
    },

    testGetSpinnerDoesntIncludeSpinWhenNotDownloading: function() {
        var view = this.makeImagesView();
        var model = new Y.maas.image.Image({downloading: false});
        var html = view.getSpinner(model);
        var node = Y.Node.create(html);
        Y.Assert.isFalse(node.hasClass('spin'));
    },

    testGetSpinnerIncludesSpinWhenDownloading: function() {
        var view = this.makeImagesView();
        var model = new Y.maas.image.Image({downloading: true});
        var html = view.getSpinner(model);
        var node = Y.Node.create(html);
        Y.Assert.isTrue(node.hasClass('spin'));
    }

}));


function create_images_view(
        regionImporting, clusterImporting, ubuntuImages,
        self, root_node_descriptor) {
    var response = Y.JSON.stringify({
        region_import_running: regionImporting,
        cluster_import_running: clusterImporting,
        resources: ubuntuImages
    });
    var view = new Y.maas.image_views.ImagesView({
        srcNode: root_node_descriptor,
        loader: '#loader',
        content: '#content',
        importer: '#importer',
        ubuntuOptions: '#ubuntu-options',
        ubuntuTable: '#ubuntu-resources',
        ubuntuMissingImages: '#missing-ubuntu-images',
        ubuntuButton: '#ubuntu-apply'});
    view.loadImages(response);
    return view;
}

namespace.suite = suite;

}, '0.1', {'requires': [
    'node-event-simulate', 'test', 'maas.testing', 'maas.enums',
    'maas.image', 'maas.image_views']}
);
