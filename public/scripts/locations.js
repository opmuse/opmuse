define(['jquery', 'inheritance', 'ajaxify', 'bind', 'domReady!'], function($, inheritance, ajaxify) {

    var instance = null;

    var Locations = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Locations allowed!');
            }

            var that = this;

            $(document).ajaxComplete(function (event, xhr) {
                var header = xhr.getResponseHeader('X-Opmuse-Location');

                if (header !== null) {
                    var locations = JSON.parse(header);

                    ajaxify.setPage(locations[0]);
                }
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Locations();
        }

        return instance;
    })();
});

