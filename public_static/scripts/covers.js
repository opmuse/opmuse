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

define(['jquery', 'inheritance', 'ws', 'domReady!'], function($, inheritance, ws) {

    "use strict";

    var instance = null;

    var Covers = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Covers allowed!');
            }

            var that = this;

            // minimum ms two cover updates must be apart,
            // basically for the transition/animation to
            // have time to complete, also to avoid blinking effects..
            that.coverMinUpdate = 1000;

            that.initImages();

            $('#main').on('ajaxifyInit', function (event) {
                that.initImages();
            });

            that.times = {};

            ws.on(['covers.album.update', 'covers.artist.update'], function (id) {
                var oldTime = null;

                var type;

                if (this.event == 'covers.album.update') {
                    type = "album";
                } else {
                    type = "artist";
                }

                var key = type + "_" + id;

                if (key in that.times) {
                    oldTime = that.times[key];
                }

                var newTime = new Date().getTime();

                that.times[key] = newTime;

                var time = 0;

                if (oldTime !== null) {
                    if (newTime - oldTime < that.coverMinUpdate) {
                        time = that.coverMinUpdate;
                    }
                }

                setTimeout(function () {
                    that.refresh($("#" + type + "_cover_" + id));
                }, time);
            });

            $(document).on('click.covers', "a.remove-cover", function (event) {
                $.ajax($(this).attr('href'));
                return false;
            });
        },
        /**
         * defer loading of cover images
         */
        initImages: function () {
            $(".cover-container").each(function () {
                var img = $(this).find('img');
                var src = $(this).data('src');

                if (typeof src != 'undefined' && src !== null) {
                    img.attr('src', src);
                }
            });
        },
        refresh: function (container) {
            var img = container.find("img");

            if (img.length == 2) {
                $(img.get(0)).remove();
                img = $(img.get(1));
            } else {
                img = $(img.get(0));
            }

            img.removeClass("cover-overlay");

            var overlay = img.clone()
                .attr("src", img.attr("src") + "&refresh=" + Math.random())
                .addClass("cover-overlay");

            container.append(overlay)

            overlay.removeClass("cover-hide");

            img.addClass("cover-hide");
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Covers();
        }

        return instance;
    })();
});
