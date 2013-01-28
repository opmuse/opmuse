define(['jquery', 'inheritance', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Layout = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Layout allowed!');
            }

            $("#panel-handle").click(function (event) {
                if ($("#panel").hasClass("open")) {
                    $("#panel").removeClass("open");
                    $("#panel").css("margin-bottom", $("#panel").data("margin-bottom"));
                } else {
                    $("#panel").addClass("open");
                    var marginBottom = $("#panel").css("margin-bottom");
                    $("#panel").data("margin-bottom", marginBottom);
                    $("#panel").css("margin-bottom", 0);
                }
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Layout();
        }

        return instance;
    })();
});

