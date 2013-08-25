define(['jquery', 'inheritance', 'bind', 'bootstrap/button', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Button = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Button allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $(".dropdown-toggle").unbind('click.ajaxify');
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Button();
        }

        return instance;
    })();
});
