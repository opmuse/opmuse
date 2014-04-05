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

"use strict";

var version;

if (typeof opmuseGlobals != 'undefined' && opmuseGlobals !== null) {
    version = opmuseGlobals.version;
} else {
    version = 1;
}

var require = {
    baseUrl: "/static/scripts/",
    urlArgs: "version=" + version,
    paths: {
        'jquery.nanoscroller': 'lib/jquery.nanoscroller',
        'jquery.fileupload': 'lib/jquery.fileupload',
        'jquery.ui.widget': 'lib/jquery.ui.widget',
        'jquery': 'lib/jquery',
        'bootstrap': 'lib/bootstrap',
        'domReady': 'lib/domReady',
        'sprintf': 'lib/sprintf',
        'moment': 'lib/moment',
        'matchMedia': 'lib/matchMedia',
        'jquery.ui': 'lib/jquery.ui',
        'typeahead': 'lib/typeahead',
        'modernizr': 'lib/modernizr'
    },
    shim: {
        'typeahead': ['jquery'],
        'jquery.ui': ['jquery'],
        'bootstrap/popover': ['bootstrap/tooltip'],
        'bootstrap/button': ['bootstrap/dropdown'],
        'jquery.nanoscroller': ['jquery']
    },
    waitSeconds: 30
};
