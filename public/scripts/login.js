define(['jquery', 'inheritance', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Login = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Login allowed!');
            }

            var that = this;

            $('#top').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            if ($(".login").length > 0) {
                $(".login, .home").unbind('click.ajaxify');
            }
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Login();
        }

        return instance;
    })();
});

