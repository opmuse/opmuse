require(['jquery'], function($) {
    $.ajaxSetup({
        // repoze.who middleware expects content-type to be set :/
        headers: { 'Content-type': 'text/plain' }
    });

    require([
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
        'you'
    ], function () {
        $("#overlay").remove();
        $('body').trigger('loadFinish');
    });
});
