define(['jquery', 'inheritance', 'bind', 'domReady!'], function($, inheritance) {

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
                }
            });
        },
        isRelative: function (href) {
            return !/^http(s)?:\/\//.test(href);
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Ajaxify();
        }

        return instance;
    })();
});


