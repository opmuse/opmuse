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
        'ajaxify',
        'sprintf',
        'domReady!'
    ], function ($, inheritance, ajaxify) {

    'use strict';

    var instance = null;

    var Filters = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Filters allowed!');
            }

            var that = this;

            $('#main').on('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            var that = this;

            $('.filters .filter-value a')
                .data('ajaxify', false)
                .click(function (event) {
                    that.reloadPage($(this).siblings('input'));
                    return false;
                }
            );

            $('.filters .filter-value input').keyup(function (event) {
                if (event.keyCode == 13) {
                    $(this).siblings('.filter-button').click();
                }

                return false;
            });
        },
        reloadPage: function (input) {
            var href = $(input).siblings('.filter-button').attr('href');
            var value = $(input).val();

            if (value === '') {
                return false;
            }

            ajaxify.setPage(sprintf('%s&filter_value=%s', href, value));
        }
    });

    return (function () {
        if (instance === null) {
            instance = new Filters();
        }

        return instance;
    })();
});
