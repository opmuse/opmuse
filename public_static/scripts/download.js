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

define(['jquery', 'inheritance', 'bootstrap/popover', 'domReady!'], function($, inheritance) {

    "use strict";

    var instance = null;

    var Download = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Download allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $('.download').data('ajaxify', false);

            $('.download').each(function () {
                var button = this;

                var url = $(button).attr("href");

                var ext = url.split(".").pop();

                var options = {
                    html: true,
                    placement: "top",
                    trigger: "hover",
                    container: "#main",
                };

                if (['png', 'jpg', 'gif', 'jpeg'].indexOf(ext) != -1) {
                    options.content = $("<img>").attr("src", url);
                    $(button).popover(options);
                } else if (['txt', 'sfv', 'nfo', 'm3u', 'cue', 'log'].indexOf(ext) != -1) {
                    $.ajax(url, {
                        success: function (data) {
                            options.content = $("<pre>").append(data);
                            $(button).popover(options);
                        }
                    });
                }
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Download();
        }

        return instance;
    })();
});

