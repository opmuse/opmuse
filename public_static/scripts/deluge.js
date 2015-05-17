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

define([
        'jquery',
        'inheritance',
        'messages',
        'domReady!'
    ], function ($, inheritance, messages) {

    'use strict';

    var instance = null;

    var Deluge = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Deluge allowed!');
            }

            var that = this;

            $('#main').on('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $('#deluge .torrent-import').click(function () {
                var button = $(this);
                var url = button.data('import-url');

                $.ajax(url, {
                    success: function (data, textStatus, xhr) {
                        button.closest('tr').find('.status span').text(data.status);
                        button.attr('disabled', 'disabled');
                    },
                    error: function (xhr) {
                        messages.danger('Failed to make request');
                    }
                });
            });
        }
    });

    return (function () {
        if (instance === null) {
            instance = new Deluge();
        }

        return instance;
    })();
});