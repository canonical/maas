const glob = require('glob');
const path = require('path');
const UglifyJSPlugin = require('uglifyjs-webpack-plugin');


module.exports = {
    entry: {
        vendor: [].concat(
            glob.sync('./src/maasserver/static/js/angular/3rdparty/*.js')
        ),
        maas: ['babel-polyfill', 'macaroon-bakery', './src/maasserver/static/js/angular/entry.js']
    },
    output: {
        path: path.resolve(__dirname, 'src/maasserver/static/js/bundle'),
        filename: '[name]-min.js'
    },
    mode: 'development',
    // This creates a .map file for debugging each bundle.
    devtool: 'source-map',
    module: {
        rules: [{
            test: /\.js$/,
            loader: 'babel-loader',
            query: {
                presets: ['@babel/preset-env', '@babel/preset-react']
            }
        }]
    }
};
