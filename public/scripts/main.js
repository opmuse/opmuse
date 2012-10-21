require(['jquery'], function($) {
    $.ajaxSetup({
        // repoze.who middleware expects content-type to be set :/
        headers: { 'Content-type': 'text/plain' }
    });

    require([
        'layout',
        'ajaxify',
        'queue',
        'player',
        'search',
        'tag',
        'logout',
        'library',
        'login',
        'upload',
        'messages',
        'locations'
    ], function () {
        $('body').trigger('loadFinish');
    });
});
