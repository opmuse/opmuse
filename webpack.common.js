const path = require('path');
const webpack = require('webpack');
const MiniCssExtractPlugin = require('mini-css-extract-plugin');
const OptimizeCSSAssetsPlugin = require('optimize-css-assets-webpack-plugin');
const TerserJSPlugin = require('terser-webpack-plugin');
const FixStyleOnlyEntriesPlugin = require("webpack-fix-style-only-entries");
const ManifestPlugin = require('webpack-manifest-plugin');

module.exports = {
    entry: {
        js_init: './javascript/init.js',
        js_main: './javascript/main.js',
        css_main: './less/main.less',
        assets: './webpack-asset-entries.js'
    },
    output: {
        filename: '[name].[contenthash].js',
        path: path.resolve(__dirname, 'public_static/build/'),
        publicPath: '/static/build/'
    },
    resolve: {
        modules: [
            "node_modules",
        ],
        alias: {
            'opmuse': path.resolve(__dirname, 'javascript'),
            'jquery.nanoscroller': path.resolve(__dirname,
                'node_modules/nanoscroller/bin/javascripts/jquery.nanoscroller.js'),
            'jquery.fileupload': path.resolve(__dirname,
                'node_modules/blueimp-file-upload/js/jquery.fileupload.js'),
            'jquery.ui.widget': path.resolve(__dirname, 'node_modules/jquery-ui/ui/widget.js'),
            'jquery': path.resolve(__dirname, 'node_modules/jquery/dist/jquery.js'),
            'moment': path.resolve(__dirname, 'node_modules/momentjs/moment.js'),
            'jquery.ui': path.resolve(__dirname, 'node_modules/jquery-ui/ui/'),
            'bloodhound': path.resolve(__dirname, 'node_modules/typeahead.js/dist/bloodhound.js'),
            'typeahead': path.resolve(__dirname,
                'node_modules/typeahead.js/dist/typeahead.jquery.js'),
            'modernizr': path.resolve(__dirname, 'node_modules/modernizr/modernizr.js'),
            'bootstrap-growl': path.resolve(__dirname,
                'node_modules/bootstrap-growl/jquery.bootstrap-growl.js'),
        }
    },
    optimization: {
        minimizer: [new TerserJSPlugin({}), new OptimizeCSSAssetsPlugin({})],
    },
    plugins: [
        new webpack.ProvidePlugin({
            'jQuery': 'jquery',
            '$': 'jquery',
            'sprintf': ['sprintf', 'sprintf'],
        }),
        new ManifestPlugin({
            fileName: path.resolve(__dirname, 'cache/webpack-manifest.json'),
        }),
        new MiniCssExtractPlugin({
            filename: '[name].[contenthash].css',
            chunkFilename: '[id].css',
        }),
        new FixStyleOnlyEntriesPlugin(),
    ],
    module: {
        rules: [
            {
                test: /modernizr\/modernizr\.js$/,
                loader: "imports-loader?this=>window!exports-loader?window.Modernizr"
            },
            {
                test: /typeahead\.js\/dist\/typeahead\.jquery\.js$/,
                loader: "imports-loader?window.jQuery=jquery,Bloodhound=bloodhound"
            },
            {
                test: /typeahead\.js\/dist\/bloodhound\.js$/,
                loader: "imports-loader?window.jQuery=jquery"
            },
            {
                test: /\.less$/,
                use: [
                    {
                        loader: MiniCssExtractPlugin.loader,
                    },
                    {
                        loader: 'css-loader',
                    },
                    {
                        loader: 'less-loader'
                    },
                ]
            },
            {
                test: /\.js$/,
                loader: 'babel-loader',
                options: {
                    presets: ['@babel/preset-env']
                }
            },
            {
                test: /\.(png|jpe?g|gif|svg|eot|ttf|woff|woff2)$/,
                loader: 'file-loader',
                options: {
                    name: '[path][name].[contenthash].[ext]',
                },
            },
        ]
    }
};
