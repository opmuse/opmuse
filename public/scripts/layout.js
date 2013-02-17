define(['jquery', 'inheritance', 'storage', 'domReady!'], function($, inheritance, storage) {

    var Panel = Class.extend({
        init: function () {
            var panelOpen = storage.get('layout.panel.open');

            var that = this;

            this.panel = $("#panel");

            $("#panel-handle").click(function (event) {
                if (that.panel.hasClass("open")) {
                    that.close();
                } else {
                    that.open();
                }
            });

            if (panelOpen === true) {
                that.open();
            }
        },
        open: function () {
            this.panel.addClass("open");
            this.panel.data("margin-bottom", this.panel.css("margin-bottom"));
            this.panel.css("margin-bottom", 0);

            storage.set('layout.panel.open', true);
        },
        close: function () {
            this.panel.removeClass("open");
            this.panel.css("margin-bottom", this.panel.data("margin-bottom"));

            storage.set('layout.panel.open', false);
        }
    });

    var instance = null;

    var Layout = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Layout allowed!');
            }

            this.panel = new Panel();
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Layout();
        }

        return instance;
    })();
});

