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

define(['jquery', 'inheritance', 'ajaxify', 'bind', 'domReady!'], function($, inheritance, ajaxify) {

    "use strict";

    var instance = null;

    var Locations = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Locations allowed!');
            }

            var that = this;

            $(document).ajaxComplete(function (event, xhr) {
                var header = xhr.getResponseHeader('X-Opmuse-Location');

                if (header !== null) {
                    var locations = JSON.parse(header);

                    ajaxify.setPage(locations[0]);
                }
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Locations();
        }

        return instance;
    })();
});

