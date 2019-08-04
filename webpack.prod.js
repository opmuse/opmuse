const path = require('path');
const merge = require('webpack-merge');
const {get_conf} = require('./webpack.common.js');

var defaultFilename = '[name].[contenthash]';
var common = get_conf(defaultFilename);

module.exports = merge(common, {
    mode: 'production',
    output: {
        path: path.resolve(__dirname, 'build/public_static/build'),
    }
});
