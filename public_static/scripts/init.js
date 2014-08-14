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

'use strict';

var version;

if (typeof opmuseGlobals != 'undefined' && opmuseGlobals !== null) {
    version = opmuseGlobals.version;
} else {
    version = 1;
}

var require = {
    baseUrl: '/static/scripts/',
    urlArgs: 'version=' + version,
    paths: {
        'jquery.nanoscroller': 'lib/jquery.nanoscroller',
        'jquery.fileupload': 'lib/jquery.fileupload',
        // included twice, also in jquery.ui
        'jquery.ui.widget': 'lib/jquery.ui.widget',
        'jquery': 'lib/jquery',
        'bootstrap': 'lib/bootstrap',
        'domReady': 'lib/domReady',
        'sprintf': 'lib/sprintf',
        'moment': 'lib/moment',
        'matchMedia': 'lib/matchMedia',
        'jquery.ui': 'lib/jquery.ui',
        'typeahead': 'lib/typeahead',
        'modernizr': 'lib/modernizr',
        'bootstrap-growl': 'lib/bootstrap-growl',
        'inheritance': 'lib/inheritance'
    },
    shim: {
        'bootstrap-growl': ['jquery'],
        'typeahead': ['jquery'],
        'jquery.ui': ['jquery'],
        'bootstrap/popover': ['jquery', 'bootstrap/tooltip'],
        'bootstrap/button': ['jquery', 'bootstrap/dropdown'],
        'bootstrap/affix': ['jquery'],
        'bootstrap/alert': ['jquery'],
        'bootstrap/carousel': ['jquery'],
        'bootstrap/collapse': ['jquery'],
        'bootstrap/dropdown': ['jquery'],
        'bootstrap/modal': ['jquery'],
        'bootstrap/scrollspy': ['jquery'],
        'bootstrap/tab': ['jquery'],
        'bootstrap/tests': ['jquery'],
        'bootstrap/tooltip': ['jquery'],
        'bootstrap/transition': ['jquery'],
        'jquery.nanoscroller': ['jquery']
    },
    waitSeconds: 30
};

document.addEventListener('DOMContentLoaded', function () {
    /**
     * reset scroll and set overlay to size of viewport before we do anything else,
     * even before we load requirejs and jquery
     */
    (function () {
        window.scrollTo(0, 0);

        var overlay = document.getElementById('overlay');

        overlay.setAttribute('style',
            'width: ' + window.innerWidth + 'px; ' +
            'height: ' + window.innerHeight + 'px'
        );
    })();
}, false);
