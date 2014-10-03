/* Copyright 2014 Canonical Ltd.  This software is licensed under the
 * GNU Affero General Public License version 3 (see the file LICENSE).
 *
 * Image views.
 *
 * @module Y.maas.image_views
 */

YUI.add('maas.image_views', function(Y) {

Y.log('loading maas.image_views');
var module = Y.namespace('maas.image_views');

var BOOT_RESOURCE_TYPE = Y.maas.enums.BOOT_RESOURCE_TYPE;


/**
 * A base view class to display a set of Images (Y.maas.image.Image).
 *
 * It will load the list of images (in this.modelList) when rendered
 * for the first time and changes to this.modelList will trigger
 * re-rendering.
 *
 * You can provide your custom rendering method by defining a 'render'
 * method (also, you can provide methods named 'loadImagesStarted' and
 * 'loadImagesEnded' to customize the display during the initial loading of the
 * visible images and a method named 'displayGlobalError' to display a message
 * when errors occur during loading).
 *
 */
module.ImageListLoader = Y.Base.create('imageListLoader', Y.View, [], {

    initializer: function(config) {
        this.modelList = new Y.maas.image.ImageList();
        this.loaded = false;
    },

    render: function () {
    },

    /**
     * Add a loader, a Y.IO object. Events fired by this IO object will
     * be followed, and will drive updates to this object's model.
     *
     * It may be wiser to remodel this to consume a YUI DataSource. That
     * would make testing easier, for one, but it would also mean we can
     * eliminate our polling code: DataSource has support for polling
     * via the datasource-polling module.
     *
     * @method addLoader
     */
    addLoader: function(loader) {
        loader.on("io:start", this.loadImagesStarted, this);
        loader.on("io:end", this.loadImagesEnded, this);
        loader.on("io:failure", this.loadImagesFailed, this);
        loader.on("io:success", function(id, request) {
            this.loadImages(request.responseText);
        }, this);
    },

    /**
     * Load the images from the given data.
     *
     * @method loadImages
     */
    loadImages: function(data) {
        try {
            var parsed = JSON.parse(data);
            this.regionImportRunning = parsed.region_import_running;
            this.clusterImportRunning = parsed.cluster_import_running;
            this.mergeImages(parsed.resources);
        }
        catch(e) {
            this.loadImagesFailed();
        }
        this.loaded = true;
        this.render();
    },

    /**
     * Process an array of images, merging them into modelList with the
     * fewest modifications possible.
     *
     * @method mergeImages
     */
    mergeImages: function(images) {
        var self = this;
        var imagesByID = {};
        Y.Array.each(images, function(image) {
            imagesByID[image.id] = image;
        });
        var modelsByID = {};
        this.modelList.each(function(model) {
            modelsByID[model.get("id")] = model;
        });

        Y.each(imagesByID, function(image, id) {
            var model = modelsByID[id];
            if (Y.Lang.isValue(model)) {
                // Compare the image and the model.
                var modelAttrs = model.getAttrs();
                var modelChanges = {};
                Y.each(modelAttrs, function(value, key) {
                    if (image[key] !== value) {
                        modelChanges[key] = image[key];
                    }
                });
                // Update the image.
                model.setAttrs(modelChanges);
            }
            else {
                // Add the image.
                self.modelList.add(image);
            }
        });

        Y.each(modelsByID, function(model, id) {
            // Remove models that don't correspond to a image.
            if (!Y.Object.owns(imagesByID, id)) {
                self.modelList.remove(model);
            }
        });
    },

   /**
    * Function called if an error occurs during the initial loading.
    *
    * @method displayGlobalError
    */
    displayGlobalError: function (error_message) {
    },

   /**
    * Function called when the Image list starts loading.
    *
    * @method loadImagesStarted
    */
    loadImagesStarted: function() {
    },

   /**
    * Function called when the Image list has loaded.
    *
    * @method loadImagesEnded
    */
    loadImagesEnded: function() {
    },

    /**
     * Function called when the Image list failed to load.
     *
     * @method loadImagesFailed
     */
    loadImagesFailed: function() {
        this.displayGlobalError('Unable to load boot images.');
    }

});

/**
 * A customized view based on ImageListLoader that will display the
 * images view.
 */
module.ImagesView = Y.Base.create(
    'imagesView', module.ImageListLoader, [], {

    regionImportingText: 'Step 1/2: Region importing',
    clusterImportingText: 'Step 2/2: Clusters importing',


    initializer: function(config) {
        this.srcNode = Y.one(config.srcNode);
        this.loader = this.srcNode.one(config.loader);
        this.content = this.srcNode.one(config.content);
        this.importer = this.srcNode.one(config.importer);
        this.ubuntuOptions = this.srcNode.one(config.ubuntuOptions);
        this.ubuntuSpinner = this.srcNode.one(config.ubuntuSpinner);
        this.ubuntuTable = this.srcNode.one(config.ubuntuTable);
        this.ubuntuMissingImages = this.srcNode.one(config.ubuntuMissingImages);
        this.ubuntuButton = this.srcNode.one(config.ubuntuButton);
    },

   /**
    * Return all Ubuntu images.
    *
    * @ method getUbuntuImages
    */
    getUbuntuImages: function() {
        images = this.modelList.filter(function(model) {
            return model.get('rtype') === BOOT_RESOURCE_TYPE.SYNCED &&
                model.get('name').indexOf('ubuntu/') === 0;
        });
        // Sort the images decending, so newest Ubuntu version is on top.
        images.sort(function(a, b) {
            return -(a.get('title').localeCompare(b.get('title')));
        });
        return images;
    },

   /**
    * Display images page.
    *
    * @method render
    */
    render: function () {
        if(!this.loaded) {
            this.loader.removeClass('hidden');
            this.content.addClass('hidden');
        } else {
            this.loader.addClass('hidden');
            this.content.removeClass('hidden');
        }
        this.renderImporting();
        this.renderUbuntuView();
    },

   /**
    * Render the importing header.
    *
    * @method renderUbuntuView
    */
    renderImporting: function() {
        var importingText = this.importer.one('.importing-text');
        if(!this.regionImportRunning && !this.clusterImportRunning) {
            this.importer.addClass('hidden');
            importingText.setContent('');
        } else if (this.regionImportRunning) {
            this.importer.removeClass('hidden');
            importingText.setContent(this.regionImportingText);
        } else if (this.clusterImportRunning) {
            this.importer.removeClass('hidden');
            importingText.setContent(this.clusterImportingText);
        }
    },

   /**
    * Render the Ubuntu section of the view.
    *
    * @method renderUbuntuView
    */
    renderUbuntuView: function() {
        if(this.regionImportRunning) {
            if(Y.Lang.isValue(this.ubuntuOptions)) {
                this.ubuntuOptions.addClass('hidden');
            }
            if(Y.Lang.isValue(this.ubuntuButton)) {
                this.ubuntuButton.addClass('hidden');
            }
        } else {
            if(Y.Lang.isValue(this.ubuntuOptions)) {
                this.ubuntuOptions.removeClass('hidden');
            }
            if(Y.Lang.isValue(this.ubuntuButton)) {
                this.ubuntuButton.removeClass('hidden');
            }
        }
        var ubuntuImages = this.getUbuntuImages();
        if(ubuntuImages.length === 0) {
            this.ubuntuMissingImages.removeClass('hidden');
            this.ubuntuTable.addClass('hidden');
            this.updateUbuntuButton(false);
        } else {
            this.ubuntuMissingImages.addClass('hidden');
            this.ubuntuTable.removeClass('hidden');
            this.updateUbuntuButton(true);
        }
        var self = this;
        var innerTable = "";
        Y.each(ubuntuImages, function(model) {
            innerTable += "<tr><td>" + self.getSpinner(model) + "</td>";
            innerTable += "<td>" + model.get('title') + "</td>";
            innerTable += "<td>" + model.get('arch') + "</td>";
            innerTable += "<td>" + model.get('size') + "</td>";
            innerTable += "<td>" + model.get('numberOfNodes') + "</td>";
            innerTable += "<td>" + model.get('lastUpdate') + "</td>";
            innerTable += "</tr>";
        });
        this.ubuntuTable.one('tbody').setHTML(innerTable);
    },

   /**
    * Update the value of the ubuntuButton.
    *
    * The value of the button can be locked meaning it should not change, this
    * is done using the data attribute lock-value. data-lock-value="true"
    *
    * @method updateUbuntuButton
    */
    updateUbuntuButton: function(showApply) {
        if(!Y.Lang.isValue(this.ubuntuButton)) {
            return;
        }
        if(this.ubuntuButton.getData('lock-value') === "true") {
            return;
        }
        if(showApply) {
            this.ubuntuButton.set('value', 'Apply changes');
        }
        else {
            this.ubuntuButton.set('value', 'Import images');
        }
    },

   /**
    * Return the HTML for the downloading spinner for the given model.
    *
    * @method getSpinner
    */
    getSpinner: function(model) {
        // Spinner is not rendered when the model is complete.
        if(model.get('complete')) {
            return '';
        }
        html = '<div title="' + model.get('status') + '" class="spinner';
        if(model.get('downloading')) {
            html += ' spin';
        }
        html += '"></div>';
        return html;
    }
});

}, '0.1', {'requires': [
    'view', 'io', 'maas.enums', 'maas.image']}
);
