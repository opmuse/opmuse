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

define(['jquery', 'inheritance', 'sprintf', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Storage = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Storage allowed!');
            }

            this.storage = localStorage;
            this.typeKeyFormat = '__type__.%s';
        },
        set: function (key, value) {
            this.storage.setItem(key, value);
            this.storage.setItem(sprintf(this.typeKeyFormat, key), typeof value);
        },
        get: function (key) {
            var type = this.storage.getItem(sprintf(this.typeKeyFormat, key));
            var value = this.storage.getItem(key);

            if (type == 'boolean') {
                value = value == 'true' ? true : false;
            } else if (type == 'number') {
                value = parseFloat(value);
            }

            return value;
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Storage();
        }

        return instance;
    })();
});


