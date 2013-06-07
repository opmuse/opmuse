require(['jquery'], function($) {
    $.ajaxSetup({
        // repoze.who middleware expects content-type to be set :/
        headers: { 'Content-type': 'text/plain' }
    });

    require([
        'collapse',
        'layout',
        'button',
        'ajaxify',
        'queue',
        'player',
        'search',
        'edit',
        'logout',
        'library',
        'login',
        'upload',
        'messages',
        'modal',
        'popover',
        'tooltip',
        'locations',
        'you',
        'covers',
        'remotes',
    ], function () {
        $("#overlay").addClass('hide');
        $('body').trigger('loadFinish');
    });
});
