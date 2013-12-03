/*!
 * Copyright 2012-2013 Mattias Fliesberg
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

    var instance = null;

    var Covers = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Covers allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();

            ws.on('covers.artist.update', function (id) {
                that.refresh($("#artist_cover_" + id));
                that.refresh($(".artist_cover_" + id));
            });

            ws.on('covers.album.update', function (id) {
                that.refresh($("#album_cover_" + id));
            });
        },
        internalInit: function () {
            var that = this;

            $("a.remove-cover")
                .unbind('click.covers')
                .bind('click.covers', function (event) {
                    $.ajax($(this).attr('href'));

                    return false;
            });
        }, refresh: function (container) {
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
