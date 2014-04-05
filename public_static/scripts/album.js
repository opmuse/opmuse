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

define(['jquery', 'inheritance', 'modernizr', 'domReady!'], function($, inheritance) {

    "use strict";

    var instance = null;

    /**
     * note that this handles both albums and artists.
     */
    var Album = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Album allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            // because we have no hover on touch devices disable click
            // on cover for going to album/artist page. you'll have to click
            // the name/title instead.
            if (Modernizr.touch) {
                $(".album figure > a, .artist figure > a").on('click', function (event) {
                    return false;
                });
            }

            $(".album figure, .artist figure").on('mouseover', function (event) {
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
    });

    return (function() {
        if (instance === null) {
            instance = new Album();
        }

        return instance;
    })();
});
