/* Javascript utilities to create a version switcher widget.

This is mostly done, but not limited to support creating links
between the different versions of the MAAS documentation on
maas.io.

*/

function page_exists(url) {
    // Returns wether a page at the give URL exists or not.
    var result = false;
    $.ajax({
        type: 'HEAD',
        url: url,
        async: false,
        success: function () {
            result = true;
        }
    });
    return result;
};

function doc_page(version, doc_prefix) {
    // Returns the URL of the page equivalent to the current page but from
    // the given version of the documentation.
    // e.g. if the current page is 'http://host/<doc_prefix>1.6/somepage.html', calling
    // doc_page('1.7') will return 'http://host/<doc_prefix>1.7/somepage.html'.
    var pattern = new RegExp('\/' + doc_prefix + '([\\d\\.]*)\/')
    var newpathname = window.location.pathname.replace(
        pattern, '/' + doc_prefix + version + '/');
    return window.location.origin + newpathname + window.location.hash;
};

function doc_homepage(version, doc_prefix) {
    // Returns the URL of the homepage for the documentation of the given
    // version.
    return window.location.origin + '/' + doc_prefix + version + '/';
};


function set_up_version_switcher(selector, doc_prefix) {
    // Create version switcher widget.
    $(selector).replaceWith($('\
        <h3 class="p-heading--four">Version</h3> \
        <select id="id_sidebar_release" name="release"> \
        </select>'));

    release_select = $("#id_sidebar_release");

    // Request version list and populate version switcher widget with it.
    var json_url = "/" + doc_prefix + "/_static/versions.json";
    var jqxhr = $.getJSON(json_url, function(data) {
        var first = true;
        $.each(data, function (value, text) {
            var option_value = value;
            if (first) {
                // The first element corresponds to the documentation for trunk.
                option_value = '';
                first = false;
            }
            var option = $("<option></option>").attr("value", option_value).text(text);
            if (value == DOCUMENTATION_OPTIONS.VERSION) {
                option.attr('selected', 'selected');
            }
            release_select.append(option);
        });
    });

    // jqxhr.fail only exists in recent versions of jQuery;
    // it's not there with the version shipped with Sphinx
    // on Precise.
    if ($.isFunction(jqxhr.fail)) {
    	jqxhr.fail(function(jqXHR) {
	        console.log("error requesting versions file");
	        console.log(jqXHR);
	    });
    }

    // Handle version switcher change: redirect to the equivalent page in the
    // selected version of the documentation if that page exists, redirects to the
    // homepage of the selected version of the documentation otherwise.
    $("#id_sidebar_release").change(function () {
        var version = $(this).find('option:selected').val();
        var same_page_in_other_version = doc_page(version, doc_prefix);
        if (page_exists(same_page_in_other_version)) {
            window.location = same_page_in_other_version;
        } else {
            window.location = doc_homepage(version, doc_prefix);
        }
    });
};
