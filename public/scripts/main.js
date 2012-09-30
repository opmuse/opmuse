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
        'tag',
        'logout',
        'library',
        'bootstrap/bootstrap-transition',
        'bootstrap/bootstrap-alert',
        'bootstrap/bootstrap-modal',
        'bootstrap/bootstrap-dropdown',
        'bootstrap/bootstrap-scrollspy',
        'bootstrap/bootstrap-tab',
        'bootstrap/bootstrap-tooltip',
        'bootstrap/bootstrap-popover',
        'bootstrap/bootstrap-button',
        'bootstrap/bootstrap-collapse',
        'bootstrap/bootstrap-carousel',
        'bootstrap/bootstrap-typeahead'
    ]);
});
