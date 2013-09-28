requirejs.onError = function (err) {
    var overlay = document.getElementById("overlay");
    overlay.className = 'error';
    overlay.innerHTML = err;
};

require(['jquery'], function($) {
    $.ajaxSetup({
        // repoze.who middleware expects content-type to be set :/
        headers: { 'Content-type': 'text/plain' }
    });

    require(['ajaxify'], function () {
        require([
            'download',
            'collapse',
            'layout',
            'button',
            'queue',
            'search',
            'edit',
            'logout',
            'login',
            'upload',
            'messages',
            'modal',
            'tab',
            'popover',
            'tooltip',
            'locations',
            'you',
            'users',
            'covers',
            'remotes',
            'filters',
            'dir_table'
        ], function () {
            $("#overlay").addClass('hide');
            $('body').trigger('loadFinish');
        });
    });
});
