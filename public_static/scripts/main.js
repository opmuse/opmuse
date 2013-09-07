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
            'popover',
            'tooltip',
            'locations',
            'you',
            'users',
            'covers',
            'remotes',
            'filters',
            'album'
        ], function () {
            $("#overlay").addClass('hide');
            $('body').trigger('loadFinish');
        });
    });
});
