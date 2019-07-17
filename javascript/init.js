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

'use strict';

var version;

if (typeof opmuseGlobals != 'undefined' && opmuseGlobals !== null) {
    version = opmuseGlobals.version;
} else {
    version = 1;
}

document.addEventListener('DOMContentLoaded', function () {
    /**
     * reset scroll and set overlay to size of viewport before we do anything else,
     */
    (function () {
        window.scrollTo(0, 0);

        var overlay = document.getElementById('overlay');

        overlay.setAttribute('style',
            'width: ' + window.innerWidth + 'px; ' +
            'height: ' + window.innerHeight + 'px'
        );

        overlay.className = overlay.className + ' domcontentloaded';

        // disable scroll on scroll devices
        window.onscroll = function () {
            window.scrollTo(0, 0);
        };

        // disable scroll on touch devices
        document.body.ontouchmove = function (event) {
            event.preventDefault();
        };
    })();
}, false);
