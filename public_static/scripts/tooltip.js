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

define(['jquery', 'inheritance', 'bind', 'bootstrap/tooltip', 'domReady!'], function($, inheritance) {

    "use strict";

    var instance = null;

    var Tooltip = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Tooltip allowed!');
            }

            var that = this;

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        internalInit: function () {
            $("*[rel=tooltip]").tooltip();
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Tooltip();
        }

        return instance;
    })();
});
