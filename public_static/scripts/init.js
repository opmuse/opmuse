require.config({
    baseUrl: "/static/scripts/",
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
        'matchMedia': 'lib/matchMedia',
        'jquery.ui': 'lib/jquery.ui',
        'typeahead': 'lib/typeahead'
    },
    shim: {
        'jquery.ui': ['jquery'],
        'blur': ['jquery'],
        'bootstrap/popover': ['bootstrap/tooltip'],
        'bootstrap/button': ['bootstrap/dropdown'],
        'jquery.nanoscroller': ['jquery']
    },
    waitSeconds: 30
});

requirejs.onError = function (err) {
    var overlay = document.getElementById("overlay");
    overlay.className = 'error';
    overlay.innerHTML = err;
};
