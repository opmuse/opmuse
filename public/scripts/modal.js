define(['jquery', 'inheritance', 'bind', 'lib/bootstrap/bootstrap-modal', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Modal = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Modal allowed!');
            }

            var that = this;

            $('#content').bind('ajaxifyInit', function (event) {
                $("[data-toggle=modal]").unbind('click.ajaxify');
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Modal();
        }

        return instance;
    })();
});
