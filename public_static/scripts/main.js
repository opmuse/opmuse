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

requirejs.onError = function (err) {
    var overlay = document.getElementById("overlay");
    overlay.className = 'error';
    overlay.innerHTML = err;
};

require(['jquery'], function($) {
    $.ajaxSetup({
        // repoze.who middleware expects content-type to be set :/
        headers: { 'Content-type': 'text/plain' }
    });

    require(['ajaxify'], function () {
        require([
            'download',
            'collapse',
            'layout',
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
            'navbar'
        ], function () {
            $("#overlay").addClass('hide');
            $('body').trigger('loadFinish');
        });
    });
});
