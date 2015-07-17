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
        'inheritance',
        'messages',
        'ajaxify',
        'domReady!'
    ], function ($, inheritance, messages, ajaxify) {

    'use strict';

    var instance = null;

    var TorrentsSearch = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of TorrentsSearch allowed!');
            }

            var that = this;

            $('#main').on('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $('#torrents_search .torrent-search-query')
                .off('keyup.search-query')
                .on('keyup.search-query', function (event) {
                if (event.keyCode == 13 && $(this).val() != '') {
                    var value = $(this).val();
                    var encodedValue = encodeURIComponent(value);

                    ajaxify.setPage('/torrents/search?query=' + encodedValue);
                }

            });
        }
    });

    return (function () {
        if (instance === null) {
            instance = new TorrentsSearch();
        }

        return instance;
    })();
});