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

var require = {
    baseUrl: '/static/scripts/',
    urlArgs: 'version=' + version,
    paths: {
        'jquery.nanoscroller': '../lib/nanoscroller/bin/javascripts/jquery.nanoscroller',
        'jquery.fileupload': '../lib/blueimp-file-upload/js/jquery.fileupload',
        'jquery.ui.widget': '../lib/jquery-ui/ui/widget',
        'jquery': '../lib/jquery/dist/jquery',
        'bootstrap': '../lib/bootstrap/js/',
        'domReady': '../lib/requirejs-domReady/domReady',
        'sprintf': '../lib/sprintf/src/sprintf',
        'moment': '../lib/momentjs/moment',
        'matchMedia': '../lib/matchMedia/matchMedia',
        'jquery.ui': '../lib/jquery-ui/ui/',
        'bloodhound': '../lib/typeahead.js/dist/bloodhound',
        'typeahead': '../lib/typeahead.js/dist/typeahead.jquery',
        'modernizr': '../lib/modernizr/modernizr',
        'bootstrap-growl': '../lib/bootstrap-growl/jquery.bootstrap-growl',
        'inheritance': 'lib/inheritance'
    },
    shim: {
        'bootstrap-growl': ['jquery'],
        'typeahead': ['jquery', 'bloodhound'],
        'jquery.ui/core': ['jquery'],
        'jquery.ui/widget': ['jquery.ui/core'],
        'jquery.ui/mouse': ['jquery.ui/widget'],
        'jquery.ui/sortable': ['jquery.ui/mouse'],
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
