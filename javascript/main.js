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

/**
 * load ws and layout first so we can bind
 * on ws open event without having to wait for all
 * modules to load... should greatly reduce the risk
 * of the event firing before we listen to it
 */
import $ from 'jquery';
import ws from 'opmuse/ws';
import layout from 'opmuse/layout';

var done = function() {
    layout.unlockOverlay();
    layout.hideOverlay();

    window.onscroll = null;
    document.body.ontouchmove = null;
};

if (opmuseGlobals.authenticated) {
    $(ws).on('open', function() {
        done();
    });
} else {
    done();
}

import 'opmuse/ajaxify';
import 'opmuse/download';
import 'opmuse/collapse';
import 'opmuse/button';
import 'opmuse/queue';
import 'opmuse/search';
import 'opmuse/edit';
import 'opmuse/logout';
import 'opmuse/login';
import 'opmuse/upload';
import 'opmuse/messages';
import 'opmuse/modal';
import 'opmuse/tab';
import 'opmuse/popover';
import 'opmuse/tooltip';
import 'opmuse/locations';
import 'opmuse/settings';
import 'opmuse/users';
import 'opmuse/covers';
import 'opmuse/remotes';
import 'opmuse/filters';
import 'opmuse/navbar';
import 'opmuse/album';
import 'npm-modernizr';
import 'opmuse/dashboard';
import 'opmuse/love';
import 'opmuse/torrents_deluge';
import 'opmuse/torrents_search';

$.ajaxSetup({
    // repoze.who middleware expects content-type to be set :/
    headers: {
        'Content-type': 'text/plain'
    }
});
