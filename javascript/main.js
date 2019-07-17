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

/**
 * load ws and layout first so we can bind
 * on ws open event without having to wait for all
 * modules to load... should greatly reduce the risk
 * of the event firing before we listen to it
 */
require([
    'jquery',
    'opmuse/ws',
    'opmuse/layout'
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
    'opmuse/ajaxify',
    'opmuse/download',
    'opmuse/collapse',
    'opmuse/button',
    'opmuse/queue',
    'opmuse/search',
    'opmuse/edit',
    'opmuse/logout',
    'opmuse/login',
    'opmuse/upload',
    'opmuse/messages',
    'opmuse/modal',
    'opmuse/tab',
    'opmuse/popover',
    'opmuse/tooltip',
    'opmuse/locations',
    'opmuse/you',
    'opmuse/users',
    'opmuse/covers',
    'opmuse/remotes',
    'opmuse/filters',
    'opmuse/navbar',
    'opmuse/album',
    'modernizr',
    'opmuse/dashboard',
    'opmuse/love',
    'opmuse/torrents_deluge',
    'opmuse/torrents_search'
    ], function ($) {

    $.ajaxSetup({
        // repoze.who middleware expects content-type to be set :/
        headers: { 'Content-type': 'text/plain' }
    });
});
