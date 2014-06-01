/*!
 * Copyright 2012-2014 Mattias Fliesberg
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

define(['jquery', 'inheritance', 'storage', 'matchMedia', 'domReady!'],
        function($, inheritance, storage) {

    "use strict";

    var instance = null;

    var Offscreennav = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Offscreennav allowed!');
            }

            var that = this;

            that.gutterWidth = 12;
            that.gridCols = 12;
            that.navCols = 4;

            $('#main').on('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();

            $(window).resize(function () {
                var shown = storage.get('offscreennav.shown');

                var smallScreen = matchMedia('all and (max-width: 940px)').matches;

                if (smallScreen) {
                    $(".off-screen-nav-button").hide();
                } else {
                    $(".off-screen-nav-button").show();
                }

                if (smallScreen) {
                    that.doNoTransition(false, false);
                } else if (shown) {
                    that.doNoTransition(true, false);
                }

                that.updateSize();
            });
        },
        internalInit: function () {
            var that = this;

            if ($(".effeckt-off-screen-nav").length === 0) {
                $(".off-screen-nav-button").hide();
                return;
            }

            $(".off-screen-nav-button").click(function (event) {
                if ($(".effeckt-off-screen-nav").is('.effeckt-show')) {
                    that.close();
                } else {
                    that.open();
                }

                return false;
            });

            var shown = storage.get('offscreennav.shown');

            if (shown === null) {
                shown = true;
            }

            that.doNoTransition(shown, false);
        },
        doNoTransition: function (show, store) {
            var that = this;

            $(".effeckt-off-screen-nav, .effeckt-page-active").addClass('no-transition');

            if (show) {
                that.open(store);
            } else {
                that.close(store);
            }

            setTimeout(function () {
                $(".effeckt-off-screen-nav, .effeckt-page-active").removeClass('no-transition');
            }, 0);
        },
        open: function (store) {
            if (typeof store == 'undefined') {
                store = true;
            }

            $(".off-screen-nav-button").addClass("show");

            $(".effeckt-off-screen-nav").css('height', 'auto').addClass("effeckt-show");

            if (store) {
                storage.set('offscreennav.shown', true);
            }
        },
        close: function (store) {
            if (typeof store == 'undefined') {
                store = true;
            }

            $(".off-screen-nav-button").removeClass("show");

            $(".effeckt-off-screen-nav").removeClass("effeckt-show");

            if ($(".effeckt-off-screen-nav").is('.no-transition')) {
                $(".effeckt-off-screen-nav").css('height', '0');
            } else {
                $(".effeckt-off-screen-nav").one('transitionend', function (event) {
                    $(this).css('height', '0');
                });
            }

            if (store) {
                storage.set('offscreennav.shown', false);
            }
        },
        updateSize: function () {
            var that = this;

            var navSize;

            // when off-screen-nav isn't shown use the full page to calculate the size
            if ($(".effeckt-off-screen-nav.effeckt-show").length === 0) {
                navSize = $(".effeckt-page-active").width() * (that.navCols / that.gridCols) - that.gutterWidth;
            // when off-screen-nav is shown just use it to calculate the size
            } else {
                navSize = $(".effeckt-off-screen-nav").width();
            }

            $(".effeckt-off-screen-nav #right").width(navSize);
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Offscreennav();
        }

        return instance;
    })();
});
