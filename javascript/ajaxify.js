/*!
 * Copyright 2012-2015 Mattias Fliesberg
 *
 * This file is part of opmuse.
 *
 * opmuse is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * opmuse is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with opmuse.  If not, see <http://www.gnu.org/licenses/>.
 */

import $ from 'jquery';
import layout from 'opmuse/layout';
import 'bootstrap';

class Throb {
    constructor(brand) {
        var that = this;

        this.brand = brand;

        // animation duration as set in throbber.less
        // we want to always run one full cycle of the animation and never
        // stop in the middle of it...
        this.animationDuration = 700;

        this.active = 0;

        $(document).ajaxSend(function() {
            if (that.active == 0) {
                that.start();
            }

            that.active++;
        });

        $(document).ajaxComplete(function() {
            that.active--;

            var sinceStart = new Date().getTime() - that.startTime;

            var timeout = null;

            if (sinceStart <= that.animationDuration) {
                timeout = that.animationDuration - sinceStart;
            } else {
                timeout = that.animationDuration * Math.ceil(sinceStart / that.animationDuration) - sinceStart;
            }

            setTimeout(function() {
                if (that.active == 0) {
                    that.stop();
                }
            }, timeout);
        });
    }
    stop() {
        $(this.brand).removeClass('throb');
    }
    start() {
        this.startTime = new Date().getTime();

        $(this.brand).addClass('throb');
    }
    setError(msg) {
        $(this.brand).addClass('error').popover({
            content: $('<p>').text(msg).addClass('text-danger'),
            html: true,
            trigger: 'hover',
            container: 'body',
            placement: 'right bottom'
        });
    }
    unsetError() {
        $(this.brand).removeClass('error').popover('destroy');
    }
}

/**
 * This one listens to click events and loads the href in the content div
 * instead of reloading the full page.
 */
class Ajaxify {
    constructor() {
        var that = this;

        this.throb = new Throb('.navbar-brand');

        this.contents = ['#main', '#navbar-sub', '#navbar-main', '#spacer'];

        if ($(this.contents[0]).length == 0) {
            return;
        }

        this.selector = '#top, #queue, #main, #spacer';

        this.initialURL = document.location.href;

        this.activeRequest = null;

        // setTimeout hack to ignore initial popstate that at least chrome fires,
        // but not firefox
        setTimeout(function() {
            $(window).on('popstate', function(event) {
                var href = document.location.pathname + document.location.search;

                if (that.activeRequest !== null) {
                    that.activeRequest.abort();
                }

                if (href !== null) {
                    that.loadPage(href);
                }
            });
        });

        this.load(this.selector, false);

        $(document).on('click.ajaxify', 'a',
            function(event) {

                var ajaxify = $(this).data('ajaxify');

                if (typeof ajaxify != 'undefined' && ajaxify !== null && ajaxify === false) {
                    return;
                }

                var href = $(this).attr('href');

                if (!event.ctrlKey && that.isRelative(href)) {
                    that.setPage(href);
                } else {
                    // open external and ctrl-click in new window/tab
                    window.open(href, '_blank');
                }

                $(this).trigger('ajaxifyClick');

                // continue propagation if the link has said attribute
                return $(this).is('[data-ajaxify=continue]');
            }
        );
    }
    load(element, trigger) {
        var that = this;

        if (typeof trigger == 'undefined' || trigger === null) {
            trigger = true;
        }

        if (trigger) {
            $(this.selector).trigger('ajaxifyInit');
        }
    }
    loadPage(href) {
        var that = this;
        var contents = that.contents.join(',');

        layout.showOverlay();

        this.activeRequest = $.ajax(href, {
            success: function(data, textStatus, xhr) {
                if (typeof data != 'undefined' && data !== null && data !== '') {
                    that.setPageInDom(data);
                }

                layout.hideOverlay();
                that.activeRequest = null;
            },
            error: function(xhr) {
                var contentType = xhr.getResponseHeader('Content-Type');

                var data = null;

                if (contentType !== null && contentType.indexOf('text/plain') !== -1) {
                    // do you know of a way to change so the browser just
                    // renders text/plain instead? i dont, would be nice.
                    data = '<pre>' + xhr.responseText + '</pre>';
                } else if (xhr.statusText != 'abort') {
                    data = xhr.responseText;
                }

                if (data !== null) {
                    that.setPageInDom(data);
                }

                layout.hideOverlay();
                that.activeRequest = null;
            }
        });
    }
    setPageInDom(data) {
        var html = $($.parseHTML(data));

        document.title = $.trim(html.find('#title').text());

        var notFound = 0;

        for (var index in this.contents) {
            var content = this.contents[index];
            var newContent = html.find(content);

            if (newContent.length === 0) {
                notFound += 1;
                continue;
            }

            this.setInDom(content, newContent);
        }

        $(window).scrollTop(0);

        // if none of the contents are found we just replace the whole
        // document, this happens when there's a standard cherrypy error
        if (notFound === this.contents.length) {
            var newDoc = document.open('text/html', 'replace');
            newDoc.write(data);
            newDoc.close();
        }

        this.load(this.selector);
    }
    setInDom(content, newContent) {
        $(content).empty();

        if ($(newContent).length == 0) {
            return;
        }

        $(content)
            .append($(newContent).contents());

        this.fixAttributes(newContent, content);
    }
    fixAttributes(newContent, content) {
        // TODO adds attributes but doesn't remove no longer existing attributes
        $.each($(newContent).get(0).attributes, function(index, attribute) {
            $(content).attr(attribute.name, attribute.value);
        });
    }
    getPage(href) {
        if (!this.isRelative(href)) {
            href = this.getPathComponent(href);
        }

        return href;
    }
    setPage(href) {
        href = this.getPage(href);

        history.pushState({}, '', href);

        this.loadPage(href);
    }
    getPathComponent(href) {
        return href.match(/^http(s)?:\/\/[^\/]+(.*)/)[2];
    }
    isRelative(href) {
        return !/^http(s)?:\/\//.test(href);
    }
};

export default new Ajaxify();
