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

            $('#content').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $('.search-query').bind('keyup', function (event) {
                if (event.keyCode == 13) {
                    ajaxify.setPage('/search/' + $(this).val());
                }
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Search();
        }

        return instance;
    })();
});

