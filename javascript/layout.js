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

define([
        'jquery',
        'storage',
        'matchMedia',
        'domReady!'
    ], function ($, storage) {

    'use strict';

    class Panel {
        constructor (layout) {
            var panelOpen = storage.get('layout.panel.open');

            var that = this;

            this.layout = layout;

            this.panel = $('#panel');

            $('#panel-full').click(function (event) {
                if (matchMedia('all and (max-width: 940px)').matches) {
                    return;
                }

                if ($(that.panel).hasClass('panel-fullscreen')) {
                    that.closeFullscreen();
                } else {
                    that.openFullscreen();
                    that.open();
                }

                $(that.panel).one('transitionend', function (event) {
                    $(that.panel).trigger('panelFullscreen');
                });
            });

            $('#panel-handle').click(function (event) {
                if ($(that.panel).hasClass('panel-fullscreen')) {
                    return;
                }

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

            $(window).resize(function () {
                // @navbarCollapseWidth
                if (matchMedia('all and (max-width: 940px)').matches) {
                    that.open();
                    that.closeFullscreen();
                }
            }).resize();
        }
        openFullscreen () {
            if (this.layout.showOverlay()) {
                $(this.panel).addClass('panel-fullscreen');
            }
        }
        closeFullscreen () {
            if (this.layout.hideOverlay()) {
                $(this.panel).removeClass('panel-fullscreen');
            }
        }
        open () {
            this.panel.addClass('open');
            storage.set('layout.panel.open', true);
        }
        close () {
            this.panel.removeClass('open');
            storage.set('layout.panel.open', false);
        }
    }

    var instance = null;

    class Layout {
        constructor () {
            if (instance !== null) {
                throw Error('Only one instance of Layout allowed!');
            }

            var that = this;

            this.panel = new Panel(this);
            this.overlayed = 0;

            // initial resizing is done in init.js pre jquery and everything...
            $(window).resize(function () {
                that.resizeOverlay();
            });
        }
        resizeOverlay () {
            $('#overlay').width($(window).width());
            $('#overlay').height($(window).height());
        }
        lockOverlay () {
            $('body').removeClass('loaded');
            $('#overlay').addClass('locked');
        }
        unlockOverlay () {
            $('body').addClass('loaded');
            $('#overlay').removeClass('locked');
        }
        showOverlay () {
            if ($('#overlay').is('.locked')) {
                return false;
            }

            $(window).scrollTop(0);

            this.overlayed++;

            $('body').addClass('overlayed');
            $('#overlay').show().removeClass('hide-overlay').addClass('transparent');

            return true;
        }
        hideOverlay () {
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
                $('#overlay').addClass('hide-overlay').one('transitionend', function () {
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

    return (function () {
        if (instance === null) {
            instance = new Layout();
        }

        return instance;
    })();
});
