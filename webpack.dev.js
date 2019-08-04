const merge = require('webpack-merge');
const {get_conf} = require('./webpack.common.js');

var defaultFilename = '[name]';
var common = get_conf(defaultFilename);

module.exports = merge(common, {
    mode: 'development',
    devtool: 'source-map',
});
