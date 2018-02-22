const glob = require('glob');
const path = require('path');

module.exports = {
    entry: [].concat(
        glob.sync('./src/maasserver/static/js/*.js'),
        glob.sync('./src/maasserver/static/js/ui/*.js'),
        glob.sync('./src/maasserver/static/js/angular/*.js'),
        glob.sync('./src/maasserver/static/js/angular/controllers/*.js'),
        glob.sync('./src/maasserver/static/js/angular/directives/*.js'),
        glob.sync('./src/maasserver/static/js/angular/filters/*.js'),
        glob.sync('./src/maasserver/static/js/angular/services/*.js'),
        glob.sync('./src/maasserver/static/js/angular/factories/*.js'),
        glob.sync('./src/maasserver/static/js/angular/3rdparty/*.js')
    ),
    output: {
        path: path.resolve(__dirname, 'src/maasserver/static/js/bundle'),
        filename: 'maas.js'
    }
};
