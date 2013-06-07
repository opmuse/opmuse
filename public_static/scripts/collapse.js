define(['jquery', 'inheritance', 'bind', 'bootstrap/bootstrap-collapse', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Collapse = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Collapse allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $("[data-toggle=collapse]").unbind('click.ajaxify');
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Collapse();
        }

        return instance;
    })();
});
