define(['jquery', 'inheritance', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Download = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Download allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $('.download').unbind('click.ajaxify');
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Download();
        }

        return instance;
    })();
});

