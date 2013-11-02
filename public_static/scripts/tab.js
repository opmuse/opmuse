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

            this.setActive("pill");
            this.setActive("tab");
        },
        /**
         * if there's no active tab/pill set first tab/pill as active...
         */
        setActive: function (type) {
            var nav = $("[data-toggle=tab]").closest(".nav-" + type + "s");
            var content = nav.siblings(".tab-content");

            if (content.length > 0 && content.find(">li.active").length == 0) {
                var first = content.find(':first-child');
                var id = first.attr("id");
                nav.find("[href=#" + id + "]").tab("show");
            }
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Tab();
        }

        return instance;
    })();
});
