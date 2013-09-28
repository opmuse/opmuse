define(['jquery', 'inheritance', 'bind', 'bootstrap/tab', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Tab = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Tab allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $("[data-toggle=tab] a, [data-toggle=pill] a")
            .unbind('click.ajaxify')
            .click(function (event) {
                $(this).tab("show");

                return false;
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Tab();
        }

        return instance;
    })();
});
