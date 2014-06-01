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

define(['jquery', 'inheritance', 'ajaxify', 'domReady!'], function($, inheritance, ajaxify) {

    "use strict";

    var instance = null;

    var You = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of You allowed!');
            }

            var that = this;

            $('#main').on('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            var that = this;

            $("#you form button").click(function (event) {
                var form = $(this).closest('form');
                var data = $(form).serialize();

                $.ajax($(form).attr('action'), {
                    type: 'post',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    data: data,
                    success: function (data) {
                        ajaxify.setPageInDom(data);
                    },
                    error: function (xhr) {
                        ajaxify.setPageInDom(xhr.responseText);
                    }
                });

                return false;
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new You();
        }

        return instance;
    })();

});

