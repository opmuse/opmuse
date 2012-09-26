require(['jquery', 'less'], function($) {
    $.ajaxSetup({
        // repoze.who middleware expects content-type to be set :/
        headers: { 'Content-type': 'text/plain' }
    });

    require([
        'queue',
        'player',
        'search',
        'tag',
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
