define(['jquery', 'inheritance', 'bootstrap/popover', 'bind', 'domReady!'], function($, inheritance, popover) {

    var Throb = Class.extend({
        init: function (brand) {
            var that = this;

            this.brand = brand;

            // animation duration as set in throbber.less
            // we want to always run one full cycle of the animation and never
            // stop in the middle of it...
            this.animationDuration = 1800;

            this.active = 0;

            $(document).ajaxSend(function () {
                if (that.active == 0) {
                    that.start();
                }

                that.active++;
            });

            $(document).ajaxComplete(function () {
                that.active--;

                var sinceStart = new Date().getTime() - that.startTime;

                var timeout = null;

                if (sinceStart <= that.animationDuration) {
                    timeout = that.animationDuration - sinceStart;
                } else {
                    timeout = that.animationDuration * Math.ceil(sinceStart / that.animationDuration) - sinceStart;
                }

                setTimeout(function () {
                    if (that.active == 0) {
                        that.stop();
                    }
                }, timeout);
            });
        },
        stop: function () {
            $(this.brand).removeClass('throb');
        },
        start: function () {
            this.startTime = new Date().getTime();

            $(this.brand).addClass('throb');
        },
        setError: function (msg) {
            $(this.brand).addClass('error').popover({
                'content': $('<p>').text(msg).addClass('text-danger'),
                'html': true,
                'trigger': 'hover',
                'container': 'body',
                'placement': 'right bottom'
            });
        },
        unsetError: function () {
            $(this.brand).removeClass('error').popover('destroy');
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

            this.throb = new Throb('.navbar-brand');

            this.contents = ['#main', '#navbar-sub', '#navbar-main', '#messages'];

            if ($(this.contents[0]).length == 0) {
                return;
            }

            this.selector = '#top, #queue, #main, #messages';

            this.initialURL = document.location.href;

            this.activeRequest = null;

            // setTimeout hack to ignore initial popstate that at least chrome fires,
            // but not firefox
            setTimeout(function () {
                $(window).bind('popstate', function (event) {

                    href = document.location.pathname + document.location.search;

                    if (that.activeRequest !== null) {
                        that.activeRequest.abort();
                    }

                    if (href !== null) {
                        that.loadPage(href);
                    }
                });
            });

            this.load(this.selector, false);
        },
        load: function (element, trigger) {
            var that = this;

            if (typeof trigger == 'undefined' || trigger === null) {
                trigger = true;
            }

            $(element).find('a')
                .unbind('click.ajaxify')
                .bind('click.ajaxify', function (event) {
                var href = $(this).attr('href');

                if (!event.ctrlKey && that.isRelative(href)) {
                    that.setPage(href);
                } else {
                    // open external and ctrl-click in new window/tab
                    window.open(href, "_blank");
                }

                // continue propagation if the link has said attribute
                return $(this).is("[data-ajaxify=continue]");
            });

            if (trigger) {
                $(this.selector).trigger('ajaxifyInit');
            }
        },
        loadPage: function (href) {
            var that = this;
            var contents = that.contents.join(',');

            that.disableElements(contents);

            this.activeRequest = $.ajax(href, {
                success: function (data, textStatus, xhr) {
                    that.setPageInDom(data);
                    that.enableElements(contents);
                    that.activeRequest = null;
                },
                error: function (xhr) {
                    if (xhr.statusText != 'abort') {
                        that.setPageInDom(xhr.responseText);
                    }
                    that.enableElements(contents);
                    that.activeRequest = null;
                },
            });
        },
        setPageInDom: function (data) {
            var html = $($.parseHTML(data));

            document.title = $.trim(html.find("#title").text());

            for (var index in this.contents) {
                var content = this.contents[index];
                var newContent = html.find(content);

                this.setInDom(content, newContent);

                $(window).scrollTop(0);
            }

            this.load(this.selector);
        },
        setInDom: function (content, newContent) {
            $(content).contents().remove();

            if ($(newContent).length == 0) {
                return;
            }

            $(content)
                .append($(newContent).contents());

            $.each($(newContent).get(0).attributes, function (index, attribute) {
                $(content).attr(attribute.name, attribute.value);
            });
        },
        disableElements: function (element) {
            $(element).addClass('ajaxify-disabled');

            $(element).find("input, textarea, select").attr("disabled", "disabled");
            $(element).find('.btn, a, input').addClass('disabled');

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

            $(element).find('.btn, a, input').removeClass('disabled');

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

            history.pushState({}, "", href);

            this.loadPage(href);
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
