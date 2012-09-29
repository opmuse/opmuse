define(['jquery', 'inheritance', 'throbber', 'bind', 'domReady!'], function($, inheritance, throbber) {

    var Throb = Class.extend({
        init: function (throbber, brand) {
            var that = this;

            this.throbber = $(throbber);
            this.brand = $(brand);

            this.throb = new Throbber({
                color: '#B16848',
                size: 28,
                fade: 1500,
                rotationspeed: 10,
                lines: 10,
                strokewidth: 2.4,
            }).appendTo(this.throbber.get(0));

            this.active = 0;

            $('body').ajaxSend(function () {
                if (that.active == 0) {
                    that.start();
                }

                that.active++;
            });

            $('body').ajaxComplete(function () {
                that.active--;

                setTimeout(function () {
                    if (that.active == 0) {
                        that.stop();
                    }
                }, 500);
            });
        },
        stop: function () {
            this.throbber.hide();
            this.brand.show();

            this.throb.start();
        },
        start: function () {
            this.throbber.show();
            this.brand.hide();

            this.throb.start();
        }
    });

    var instance = null;

    /**
     * This one listens to click events and loads the href in the content div
     * instead of reloading the full page.
     */
    var Ajaxify = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Ajaxify allowed!');
            }

            var that = this;

            this.throb = new Throb('.throbber', '.brand');

            this.content = '#content';
            this.selector = '#top, #left, #content, #footer';

            this.internalInit();

            $(window).bind('hashchange', function (event) {
                var href = document.location.hash.substring(1);
                if (typeof href != 'undefined' && href != '') {
                    that.loadPage(href);
                }
            });

            $(window).trigger('hashchange');
        },
        internalInit: function () {
            var that = this;

            $(this.selector).find('a')
                .unbind('click.ajaxify')
                .bind('click.ajaxify', function (event) {
                var href = $(this).attr('href');

                if (that.isRelative(href)) {
                    document.location.hash = href;
                } else {
                    // open external links in new window/tab
                    window.open(href, "_blank");
                }
                return false;

            });

            $(this.content).trigger('ajaxifyInit');
        },
        loadPage: function (href) {
            var that = this;
            $.ajax(href, {
                success: function (data, textStatus, xhr) {
                    $(that.content).html($(data).find(that.content + ' > *'));
                    that.internalInit();
                },
                error: function () {
                }
            });
        },
        isRelative: function (href) {
            return !/^http(s)?:\/\//.test(href);
        },
    });

    return (function() {
        if (instance === null) {
            instance = new Ajaxify();
        }

        return instance;
    })();
});


