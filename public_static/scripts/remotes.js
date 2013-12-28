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

define(['jquery', 'inheritance', 'ws', 'ajaxify', 'bind', 'domReady!'], function($, inheritance, ws, ajaxify) {

    "use strict";

    var instance = null;

    var Remotes = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Remotes allowed!');
            }

            var that = this;

            ws.on('remotes.artist.fetched', function (id) {
                that.load([".remotes_artist_head_" + id, ".remotes_artist_nav_" + id]);
            });

            ws.on('remotes.album.fetched', function (id) {
                that.load([".remotes_album_head_" + id, ".remotes_album_nav_" + id]);
            });

            ws.on('remotes.track.fetched', function (id) {
                that.load([".remotes_track_head_" + id]);
            });

            ws.on('remotes.tag.fetched', function (tag_name) {
                that.load(["[data-remotes-tag='" + tag_name + "']"]);
            });
        },
        load: function (selectors) {
            var found = false;

            for (var index in selectors) {
                var selector = selectors[index];

                if ($(selector).length > 0) {
                    found = true;
                    break;
                }
            }

            if (found) {
                $.ajax(document.location.href, {
                    success: function (data, textStatus, xhr) {
                        var page = $($.parseHTML(data));

                        for (var index in selectors) {
                            var selector = selectors[index];

                            (function (selector) {
                                var element = $(selector);

                                element.addClass('remotes-hide').one('transitionend', function (event) {
                                    element.get(0).innerHTML = page.find(selector).get(0).innerHTML;

                                    ajaxify.load(selector);

                                    $(this).removeClass('remotes-hide');
                                });
                            })(selector);
                        }
                    },
                    error: function (xhr) {
                    }
                });
            }
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Remotes();
        }

        return instance;
    })();
});
