define(['jquery', 'inheritance', 'storage', 'blur', 'matchMedia', 'domReady!'], function($, inheritance, storage) {

    var Panel = Class.extend({
        init: function () {
            var panelOpen = storage.get('layout.panel.open');

            var that = this;

            this.panel = $("#panel");

            $("#panel-full").click(function (event) {
                if (matchMedia('all and (max-width: 940px)').matches) {
                    return;
                }

                if ($(that.panel).hasClass("panel-fullscreen")) {
                    $(that.panel).removeClass("panel-fullscreen");
                    $("#overlay").removeClass("transparent");
                    $("#main, #top").blurjs('remove');
                } else {
                    that.open();
                    $(that.panel).addClass("panel-fullscreen");
                    $("#overlay").addClass("transparent");
                    $("#main, #top").blurjs({
                        radius: 1
                    });
                }

                $(that.panel).one('webkitTransitionEnd transitionend', function (event) {
                    $(that.panel).trigger('panelFullscreen');
                });
            });

            $("#panel-handle").click(function (event) {
                if ($(that.panel).hasClass('panel-fullscreen')) {
                    return;
                }

                // @navbarCollapseWidth
                if (matchMedia('all and (max-width: 940px)').matches) {
                    return;
                }

                if (that.panel.hasClass("open")) {
                    that.close();
                } else {
                    that.open();
                }
            });

            if (panelOpen === true) {
                that.open();
            }

            $(window).resize(function () {
                // @navbarCollapseWidth
                if (matchMedia('all and (max-width: 940px)').matches) {
                    that.open();
                }
            }).resize();
        },
        open: function () {
            this.panel.addClass("open");
            storage.set('layout.panel.open', true);
        },
        close: function () {
            this.panel.removeClass("open");
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

