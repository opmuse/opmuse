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

            this.contents = ['#content', '#right'];

            if ($(this.contents[0]).length == 0) {
                return;
            }

            this.selector = '#top, #queue, #right, #content, #footer';

            $(window).bind('hashchange', function (event) {
                var href = that.getHref();

                if (href !== null) {
                    that.loadPage(href);
                }
            });

            $('body').bind('loadFinish', function () {
                var href = that.getHref();

                if (href === null) {
                    that.setPage('/library');
                } else {
                    $(window).trigger('hashchange');
                }
            });
        },
        getHref: function () {
            var href = document.location.hash.substring(1);

            if (typeof href == 'undefined' || href === '') {
                href = null;
            }

            return href;
        },
        internalInit: function () {
            this.load(this.selector);
        },
        load: function (element) {
            var that = this;

            $(element).find('a')
                .unbind('click.ajaxify')
                .bind('click.ajaxify', function (event) {
                var href = $(this).attr('href');

                if (!event.ctrlKey && that.isRelative(href)) {
                    that.setPage(href);
                } else if (event.ctrlKey && that.isRelative(href)) {
                    // open ctrl-click in new window/tab
                    window.open(document.location.pathname + "#" + that.getPage(href), "_blank");
                } else {
                    // open external links new window/tab
                    window.open(href, "_blank");
                }

                // continue propagation if the link has said attribute
                return $(this).is("[data-ajaxify=continue]");
            });

            $(element).trigger('ajaxifyInit');
        },
        loadPage: function (href) {
            var that = this;
            var contents = that.contents.join(',');
            that.disableElements(contents);
            $.ajax(href, {
                success: function (data, textStatus, xhr) {
                    that.setPageInDom(data);
                    that.enableElements(contents);
                },
                error: function (xhr) {
                    that.setErrorPageInDom(xhr.responseText);
                    that.enableElements(contents);
                },
            });
        },
        setErrorPageInDom: function (data) {
            $(this.contents[0]).html(data);
        },
        setPageInDom: function (data) {
            var html = $(data);
            document.title = $.trim(html.find("#title").text());
            for (var index in this.contents) {
                var content = this.contents[index];
                $(content).html(html.find(content + ' > *'));
                $(content).scrollTop(0);
            }
            this.internalInit();
        },
        disableElements: function (element) {
            $(element).addClass('ajaxify-disabled');

            $(element).find("input, textarea, select").attr("disabled", "disabled");

            $(element).find("*").bind(
                'click.ajaxify_disabled ' +
                'dblclick.ajaxify_disabled ' +
                'dragstart.ajaxify_disabled',
                function(event) {
                    return false;
                }
            ).unbind('click.ajaxify');
        },
        enableElements: function (element) {
            $(element).removeClass('ajaxify-disabled');

            $(element).find("input, textarea, select").removeAttr("disabled");

            $(element).find("*").unbind(
                'click.ajaxify_disabled ' +
                'dblclick.ajaxify_disabled ' +
                'dragstart.ajaxify_disabled'
            );
        },
        getPage: function (href) {
            if (!this.isRelative(href)) {
                href = this.getPathComponent(href);
            }

            return href;
        },
        setPage: function (href) {
            href = this.getPage(href);

            if (document.location.hash.substring(1) == href) {
                $(window).trigger('hashchange');
            } else {
                document.location.hash = href;
            }
        },
        getPathComponent: function (href) {
            return href.match(/^http(s)?:\/\/[^\/]+(.*)/)[2];
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
