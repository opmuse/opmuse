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

import $ from 'jquery';
import ajaxify from 'opmuse/ajaxify';

class Locations {
    constructor() {
        var that = this;

        that.disabled = false;

        $(document).ajaxComplete(function(event, xhr) {
            if (that.disabled) {
                return;
            }

            var location = that.getLocation(xhr);

            if (location !== null) {
                ajaxify.setPage(location);
            }
        });
    }
    enable() {
        this.disabled = false;
    }
    disable() {
        this.disabled = true;
    }
    getLocation(xhr) {
        var header = xhr.getResponseHeader('X-Opmuse-Location');

        if (header !== null) {
            var locations = JSON.parse(header);

            return locations[0];
        }

        return null;
    }
}

export default new Locations();
