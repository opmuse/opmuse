define(['jquery', 'inheritance', 'domReady!'], function($, inheritance) {
    var instance = null;

    var Tag = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Tag allowed!');
            }

            var that = this;

            $("#tag .lock").click(function (event) {
                var type = null;

                if ($(this).is(".album")) {
                    type = 'album';
                } else if ($(this).is(".artist")) {
                    type = 'artist';
                }

                var selector = "#tag ." + type + ":not(.lock)";

                $($(selector).attr("readonly", "readonly").get(0))
                    .removeAttr("readonly").bind('keyup', function (event) {
                    $(selector).val($(this).val());
                });

                return false;
            });

        },
    });

    return (function() {
        if (instance === null) {
            instance = new Tag();
        }

        return instance;
    })();

});

