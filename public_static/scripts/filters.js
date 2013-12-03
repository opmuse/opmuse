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

define(['jquery', 'inheritance', 'ajaxify', 'sprintf', 'bind', 'domReady!'], function($, inheritance, ajaxify) {

    var instance = null;

    var Filters = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Filters allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();

            setInterval(that.checkReload.bind(this), 500);
        },
        internalInit: function () {
            var that = this;

            $(".filters .filter_value input").each(function () {
                $(this).data('prev-value', $(this).val());
            });

            $(".filters .filter_value a").data('ajaxify', false);

            $(".filters .filter_value input").blur(function (event) {
                $(this).data('keydown-timestamp', null);
                that.reloadPage(this);
                return false;
            }).keyup(function (event) {
                $(this).data('keydown-timestamp', Date.now());
            });
        },
        checkReload: function () {
            var that = this;

            $(".filters .filter_value input").each(function () {
                var ts = $(this).data('keydown-timestamp');

                if (typeof ts != 'undefined' && ts !== null) {
                    if (Date.now() - ts > 2000) {
                        $(this).data('keydown-timestamp', null);
                        that.reloadPage(this);
                    }
                }
            });
        },
        reloadPage: function (input) {
            var href = $(input).closest("a").attr("href");
            var value = $(input).val();

            if (value == "") {
                return false;
            }

            var prevValue = $(input).data('prev-value');

            if (prevValue.toLowerCase() != value.toLowerCase()) {
                ajaxify.setPage(sprintf("%s&filter_value=%s", href, value));
            }
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Filters();
        }

        return instance;
    })();
});

