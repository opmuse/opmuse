require(['jquery'], function($) {
    $.ajaxSetup({
        // repoze.who middleware expects content-type to be set :/
        headers: { 'Content-type': 'text/plain' }
    });

    require([
        'download',
        'collapse',
        'layout',
        'button',
        'ajaxify',
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
        'components'
    ], function () {
        $("#overlay").addClass('hide');
        $('body').trigger('loadFinish');
    });
});
