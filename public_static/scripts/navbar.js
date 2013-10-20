define(['jquery', 'inheritance', 'bind', 'domReady!'], function ($, inheritance) {

    var instance = null;

    var Tooltip = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Navbar allowed!');
            }

            var navbar = $(".navbar-collapse");

            $('body').bind('ajaxifyInit', function (event) {
                navbar.collapse("hide");
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Tooltip();
        }

        return instance;
    })();
});
