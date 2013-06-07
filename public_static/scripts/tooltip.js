define(['jquery', 'inheritance', 'bind', 'bootstrap/bootstrap-tooltip', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Tooltip = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Tooltip allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $("a[rel=tooltip]").tooltip();
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Tooltip();
        }

        return instance;
    })();
});
