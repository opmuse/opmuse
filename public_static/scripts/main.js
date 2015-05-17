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

/**
 * load ws and layout first so we can bind
 * on ws open event without having to wait for all
 * modules to load... should greatly reduce the risk
 * of the event firing before we listen to it
 */
require([
    'jquery',
    'ws',
    'layout'
    ], function ($, ws, layout) {

    var done = function () {
        layout.unlockOverlay();
        layout.hideOverlay();

        window.onscroll = null;
        document.body.ontouchmove = null;
    };

    if (opmuseGlobals.authenticated) {
        $(ws).on('open', function () {
            done();
        });
    } else {
        done();
    }
});

require([
    'jquery',
    'ajaxify',
    'download',
    'collapse',
    'button',
    'queue',
    'search',
    'edit',
    'logout',
    'login',
    'upload',
    'messages',
    'modal',
    'tab',
    'popover',
    'tooltip',
    'locations',
    'you',
    'users',
    'covers',
    'remotes',
    'filters',
    'dir_table',
    'navbar',
    'album',
    'modernizr',
    'dashboard',
    'love',
    'deluge'
    ], function ($) {

    $.ajaxSetup({
        // repoze.who middleware expects content-type to be set :/
        headers: { 'Content-type': 'text/plain' }
    });
});

requirejs.onError = function (err) {
    var overlay = document.getElementById('overlay');
    overlay.className = 'error';
    overlay.innerHTML = err;
};
