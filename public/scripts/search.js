define(['jquery', 'inheritance', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Search = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Search allowed!');
            }

            if ($('#search').length == 0) {
                return;
            }

            $('#search').bind('keyup', function (event) {
                if (event.keyCode == 13) {
                    location.href = '/search/' + $(this).val();
                }
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Search();
        }

        return instance;
    })();
});

