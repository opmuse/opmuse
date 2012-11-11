require.config({
    baseUrl: "/scripts/",
    urlArgs: "version=" + window.opmuseGlobals.version,
    paths: {
        'jquery.fileupload': 'lib/jquery.fileupload',
        'jquery.ui.widget': 'lib/jquery.ui.widget',
        'jquery': 'lib/jquery',
        'bootstrap': 'lib/bootstrap',
        'domReady': 'lib/domReady',
        'throbber': 'lib/throbber'
    },
    shim: {
        'bootstrap/bootstrap-popover': ['bootstrap/bootstrap-tooltip']
    }
});
