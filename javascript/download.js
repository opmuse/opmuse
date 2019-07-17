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
        'bootstrap'
    ], function ($) {

    'use strict';

    var instance = null;

    class Download {
        constructor () {
            if (instance !== null) {
                throw Error('Only one instance of Download allowed!');
            }

            var that = this;

            $('#main').on('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        }
        internalInit () {
            $('.download').data('ajaxify', false);

            $('.download').each(function () {
                var button = this;

                var url = $(button).attr('href');

                var ext = url.split('.').pop();

                var options = {
                    html: true,
                    placement: 'top',
                    trigger: 'hover',
                    container: '#main',
                    content: 'Loading...'
                };

                if (['png', 'jpg', 'gif', 'jpeg'].indexOf(ext) != -1) {
                    options.content = $('<img>').attr('src', url);
                    $(button).popover(options);
                } else if (['txt', 'sfv', 'nfo', 'm3u', 'cue', 'log'].indexOf(ext) != -1) {
                    $(button).popover($.extend({}, options));

                    $(button).on('show.bs.popover', function () {
                        if ($(this).data('popovered') === true) {
                            return;
                        }

                        var popover = $(this).data('bs.popover');

                        popover.options.content = '';

                        $.ajax(url, {
                            success: function (data) {
                                popover.options.content = $('<pre>').append(data);
                                popover.setContent();
                            }
                        });

                        $(this).data('popovered', true)
                    });
                }
            });
        }
    }

    return (function () {
        if (instance === null) {
            instance = new Download();
        }

        return instance;
    })();
});
