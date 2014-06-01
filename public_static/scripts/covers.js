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

define(['jquery', 'inheritance', 'ws', 'bind', 'domReady!'], function($, inheritance, ws) {

    "use strict";

    var instance = null;

    var Covers = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Covers allowed!');
            }

            var that = this;

            that.initImages();

            $('#main').on('ajaxifyInit', function (event) {
                that.initImages();
            });

            ws.on('covers.artist.update', function (id) {
                that.refresh($("#artist_cover_" + id));
                that.refresh($(".artist_cover_" + id));
            });

            ws.on('covers.album.update', function (id) {
                that.refresh($("#album_cover_" + id));
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

            var overlay = img.clone().removeClass("cover-hide")
                .attr("src", img.attr("src") + "&refresh=" + Math.random())
                .addClass("cover-overlay");

            container.append(overlay)

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
