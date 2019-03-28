const glob = require('glob');
const path = require('path');
const UglifyJSPlugin = require('uglifyjs-webpack-plugin');


module.exports = {
    entry: {
        vendor: [].concat(
            glob.sync('./src/maasserver/static/js/angular/3rdparty/*.js')
        ),
        maas: ['babel-polyfill', 'macaroon-bakery'].concat(
            glob.sync('./src/maasserver/static/js/*.js'),
            glob.sync('./src/maasserver/static/js/ui/*.js'),
            glob.sync('./src/maasserver/static/js/angular/*.js'),
            glob.sync('./src/maasserver/static/js/angular/controllers/*.js'),
            glob.sync('./src/maasserver/static/js/angular/directives/*.js'),
            glob.sync('./src/maasserver/static/js/angular/directives/nodedetails/*.js'),
            glob.sync('./src/maasserver/static/js/angular/directives/nodelist/*.js'),
            glob.sync('./src/maasserver/static/js/angular/filters/*.js'),
            glob.sync('./src/maasserver/static/js/angular/services/*.js'),
            glob.sync('./src/maasserver/static/js/angular/factories/*.js')
        )
    },
    mode: 'development',
    // This creates a .map file for debugging each bundle.
    devtool: 'source-map',
    plugins: [
        /*
        new UglifyJSPlugin({
            parallel: true,
            cache: true,
            sourceMap: true,
            uglifyOptions: {
                // Using the 'mangle' option breaks the Angular injector.
                mangle: false
            }
        })
        */
    ],
    module: {
        rules: [{
            test: /\.js$/,
            loader: 'babel-loader',
            query: {
                presets: ['@babel/preset-env', '@babel/preset-react']
            }
        }]
    },
    output: {
        path: path.resolve(__dirname, 'src/maasserver/static/js/bundle'),
        filename: '[name]-min.js'
    }
};
