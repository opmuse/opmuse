define(['jquery', 'inheritance', 'ajaxify', 'domReady!'], function($, inheritance, ajaxify) {

    var instance = null;

    var Search = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Search allowed!');
            }

            if ($('.search-query').length == 0) {
                return;
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            var query = $("#search").data("query");

            if (typeof query == 'undefined' || query === null || query == '') {
                query = 'Search';
            }

            $('.search-query').bind('keyup', function (event) {
                if (event.keyCode == 13) {
                    ajaxify.setPage('/search/' + $(this).val());
                }
            }).attr('placeholder', query);
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Search();
        }

        return instance;
    })();
});

