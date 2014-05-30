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

define(['jquery', 'inheritance', 'locations', 'ajaxify', 'domReady!'], function($, inheritance, locations, ajaxify) {

    "use strict";

    var instance = null;

    var Login = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Login allowed!');
            }

            var that = this;

            $('#top').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            if ($("#login").length > 0) {
                $(".login, .home").data('ajaxify', false);
            }

            $("input[name=login]").focus();

            $("#login form").submit(function () {
                var data = $(this).serialize();
                var action = $(this).attr('action');

                $.ajax(action, {
                    type: 'post',
                    headers: {
                        'Content-Type': 'application/x-www-form-urlencoded'
                    },
                    data: data,
                    success: function (data, status, xhr) {
                        var location = locations.getLocation(xhr);

                        if (location !== null) {
                            document.location.href = location;
                        }

                        $("input[name=login]").focus().select();
                        $("input[name=password]").val('');
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
            instance = new Login();
        }

        return instance;
    })();
});

