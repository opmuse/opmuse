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

define(['jquery', 'inheritance', 'ws', 'ajaxify', 'logger', 'sprintf', 'bind', 'domReady!'],
    function($, inheritance, ws, ajaxify, logger) {

    "use strict";

    var instance = null;

    var Reloader = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Reloader allowed!');
            }
        },
        load: function (selectors) {
            var usedSelectors = [];

            for (var index in selectors) {
                var selector = selectors[index];

                if ($(selector).length > 0) {
                    if (!$(selector).hasClass('reloader')) {
                        logger.log(sprintf('Missing reloader class on %s!', selector));
                        continue;
                    }

                    usedSelectors.push(selector);
                }
            }

            if (usedSelectors.length > 0) {
                $.ajax(document.location.href, {
                    success: function (data, textStatus, xhr) {
                        var page = $($.parseHTML(data));

                        for (var index in usedSelectors) {
                            var selector = usedSelectors[index];

                            (function (selector) {
                                var element = $(selector);

                                element.addClass('reloader-hide').one('transitionend', function (event) {
                                    element.get(0).innerHTML = page.find(selector).get(0).innerHTML;

                                    ajaxify.load(selector);

                                    $(this).removeClass('reloader-hide');
                                });
                            })(selector);
                        }
                    },
                    error: function (xhr) {
                    }
                });
            }
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Reloader();
        }

        return instance;
    })();
});
