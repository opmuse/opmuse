define(['jquery', 'inheritance', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Library = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Library allowed!');
            }

            $('body').bind('ajaxifyInit', function (event) {
                $(".carousel").carousel();
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Library();
        }

        return instance;
    })();
});

