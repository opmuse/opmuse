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
        'ws',
        'reloader',
        'modernizr',
        'domReady!'
    ], function ($, ws, reloader) {

    'use strict';

    var instance = null;

    /**
     * note that this handles both albums and artists.
     */
    class Album {
        constructor () {
            if (instance !== null) {
                throw Error('Only one instance of Album allowed!');
            }

            var that = this;

            that.initReloader();

            $('#main').on('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        }
        initReloader () {
            var that = this;

            var reloadTimeout = 200;

            that.reloads = [];
            that.reloadId = null;

            // to avoid unecessary loading of the page we use a timeout based
            // approach when running this in case an insert and update is
            // dispatched at the same time and/or if multiple albums are marked
            // as seen at the same time
            ws.on(['database_events.userandalbum.update', 'database_events.userandalbum.insert'],
                function (id, columns, new_values) {
                    if (columns.seen) {
                        var selector = '#album_' + new_values.album_id + ' .album-seen-container';

                        if (!(selector in that.reloads)) {
                            that.reloads.push(selector);
                        }

                        if (that.reloadId !== null) {
                            var reloadId = that.reloadId;
                            that.reloadId = null;
                            clearTimeout(reloadId);
                        }

                        that.reloadId = setTimeout(function () {
                            var reloads = that.reloads;
                            that.reloads = [];

                            reloader.load(reloads);
                        }, reloadTimeout);
                    }
                }
            );
        }
        internalInit () {
            // because we have no hover on touch devices disable click
            // on cover for going to album/artist page. you'll have to click
            // the name/title instead.
            if (Modernizr.touch) {
                $('.album figure > a, .artist figure > a').on('click', function (event) {
                    return false;
                });
            }

            $('.album figure, .artist figure').on('mouseover', function (event) {
                if ($(this).data('shown') !== true) {
                    var content = $(this).find('*[data-href]');

                    $.ajax(content.data('href'), {
                        success: function (data, textStatus, xhr) {
                            content.html(data);
                        },
                        error: function (xhr) {
                        }
                    });
                }

                $(this).data('shown', true);
            });
        }
    }

    return (function () {
        if (instance === null) {
            instance = new Album();
        }

        return instance;
    })();
});
