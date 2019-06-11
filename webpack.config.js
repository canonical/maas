const glob = require('glob');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const OptimizeCSSAssetsPlugin = require('optimize-css-assets-webpack-plugin');
const path = require('path');


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
            exclude: /node_modules/,
            query: {
                presets: ['@babel/preset-env', '@babel/preset-react']
            }
        }, {
        test: /\.(sa|sc|c)ss$/,
        use: [
          MiniCssExtractPlugin.loader,
          {
            loader: 'css-loader',
            options: {
              // This stops the asset URLs from being modified. We want them to remain as
              // relative urls e.g. url("../assets/ will not try and package the asset.
              url: false
            }
          }, {
            loader: 'sass-loader',
            options: {
              includePaths: ['node_modules']
            }
          }
        ]
      }]
    },
    optimization: {
      minimizer: [
        new OptimizeCSSAssetsPlugin({})
      ]
    },
    plugins: [
      new MiniCssExtractPlugin({
        // This file is relative to output.path above.
        filename: '../../css/build.css',
        chunkFilename: '[id].css'
      })
    ],
    resolve: {
        modules: [
            path.resolve(__dirname, 'src/maasserver/static/js/angular/'),
            'node_modules'
        ]
    },
    stats: {
      // This hides the output from MiniCssExtractPlugin as it's incredibly verbose.
      children: false
    }
};
