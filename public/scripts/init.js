require.config({
    baseUrl: "/scripts/",
    urlArgs: "version=" + window.opmuseGlobals.version,
    paths: {
        'jquery.nanoscroller': 'lib/jquery.nanoscroller',
        'jquery.fileupload': 'lib/jquery.fileupload',
        'jquery.ui.widget': 'lib/jquery.ui.widget',
        'jquery': 'lib/jquery',
        'bootstrap': 'lib/bootstrap',
        'domReady': 'lib/domReady',
        'sprintf': 'lib/sprintf',
        'moment': 'lib/moment',
        'blur': 'lib/blur',
        'matchMedia': 'lib/matchMedia'
    },
    shim: {
        'blur': ['jquery'],
        'bootstrap/bootstrap-popover': ['bootstrap/bootstrap-tooltip'],
        'bootstrap/bootstrap-button': ['bootstrap/bootstrap-dropdown'],
        'jquery.nanoscroller': ['jquery']
    },
    waitSeconds: 30
});
