define(['jquery', 'inheritance', 'ajaxify', 'domReady!'], function($, inheritance, ajaxify) {

    var instance = null;

    var Logout = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Logout allowed!');
            }

            var that = this;

            $('#navbar-main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $(".logout").unbind('click.ajaxify');
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Logout();
        }

        return instance;
    })();
});

