define(['jquery', 'inheritance', 'bind', 'bootstrap/bootstrap-popover', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Popover = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Popover allowed!');
            }

            var that = this;

            $('#content').bind('ajaxifyInit', function (event) {
                $("a[rel=popover]").popover();
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Popover();
        }

        return instance;
    })();
});
