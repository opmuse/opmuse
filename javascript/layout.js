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
import storage from 'opmuse/storage';
import 'matchmedia-polyfill';

class Panel {
    constructor(layout) {
        var panelOpen = storage.get('layout.panel.open');

        var that = this;

        this.layout = layout;

        this.panel = $('#panel');

        $(window).resize(function() {
            that.resize();
        });

        $('#panel-handle').click(function(event) {
            // @navbarCollapseWidth
            if (matchMedia('all and (max-width: 940px)').matches) {
                return;
            }

            if (that.panel.hasClass('open')) {
                that.close();
            } else {
                that.open();
            }
        });

        if (panelOpen === true) {
            that.open();
        }

        $(window).resize(function() {
            // @navbarCollapseWidth
            if (matchMedia('all and (max-width: 940px)').matches) {
                that.open();
            }
        }).resize();
    }
    open() {
        this.panel.addClass('open');
        storage.set('layout.panel.open', true);
    }
    close() {
        this.panel.removeClass('open');
        storage.set('layout.panel.open', false);
    }
    resize() {
        var windowHeight = $(window).height();
        this.panel.attr("style", '--panel-height: ' + (windowHeight / 1.2) + 'px;');
    }
}

class Layout {
    constructor() {

        var that = this;

        this.panel = new Panel(this);
        this.overlayed = 0;

        // initial resizing is done in init.js pre jquery and everything...
        $(window).resize(function() {
            that.resizeOverlay();
        });
    }
    resizeOverlay() {
        $('#overlay').width($(window).width());
        $('#overlay').height($(window).height());
    }
    lockOverlay() {
        $('body').removeClass('loaded');
        $('#overlay').addClass('locked');
    }
    unlockOverlay() {
        $('body').addClass('loaded');
        $('#overlay').removeClass('locked');
    }
    showOverlay() {
        if ($('#overlay').is('.locked')) {
            return false;
        }

        $(window).scrollTop(0);

        this.overlayed++;

        $('body').addClass('overlayed');
        $('#overlay').show().removeClass('hide-overlay').addClass('transparent');

        return true;
    }
    hideOverlay() {
        if ($('#overlay').is('.locked') || $('#overlay').is('.error')) {
            return false;
        }

        if (this.overlayed > 0) {
            this.overlayed--;
        }

        // i.e. to avoid overlay being removed on panel close when it might
        // have been shown on ajax load but not finished. e.g. two calls
        // to showOverlay() needs two calls to hideOverlay() to actually hide it.
        if (this.overlayed === 0) {
            $('body').removeClass('overlayed');
            $('#overlay').addClass('hide-overlay').one('transitionend', function() {
                $(this).hide().removeClass('initial');
            }).removeClass('transparent');

            // for when transitionend doesn't fire (e.g. on login page(
            if (!$('#overlay').is(':visible')) {
                $('#overlay').hide().removeClass('initial');
            }

            if (!$('#overlay').hasClass('initial')) {
                $('#overlay').hide();
            }
        }

        return true;
    }
}

export default new Layout();
