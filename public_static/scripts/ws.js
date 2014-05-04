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

define(['jquery', 'inheritance', 'logger', 'ajaxify', 'sprintf', 'bind', 'domReady!'],
        function($, inheritance, logger, ajaxify) {

    "use strict";

    var instance = null;

    var Ws = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Ws allowed!');
            }

            var that = this;

            that.events = {};

            if (!opmuseGlobals.authenticated) {
                return;
            }

            var host = null;

            if (opmuseGlobals.ws_port !== null) {
                host = sprintf("%s:%d", document.location.hostname, opmuseGlobals.ws_port);
            } else {
                host = document.location.host;
            }

            var scheme = null;

            if (document.location.protocol == 'https:') {
                scheme = 'wss';
            } else {
                scheme = 'ws';
            }

            that.unloaded = false;

            that.url = scheme + '://' + host + '/ws';

            that.internalInit();
        },
        internalInit: function () {
            var that = this;

            if (!("WebSocket" in window)) {
                ajaxify.throb.setError("Browser doesn't support websockets, things will not work as expected.");
                return;
            }

            that.socket = new WebSocket(that.url);

            var errTimeout = 1000;

            var errHandler = function () {
                if (that.socket.readyState === WebSocket.CONNECTING) {
                    logger.log('ws connecting...');
                    setTimeout(errHandler, errTimeout);
                } else if (that.socket.readyState !== WebSocket.OPEN) {
                    ajaxify.throb.setError("Couldn't establish websocket connection, might be firewall issues.");
                }
            };

            setTimeout(errHandler, errTimeout);

            that.socket.onmessage = function (event) {
                var data = JSON.parse(event.data);

                if (data.event in that.events) {
                    for (var index in that.events[data.event]) {
                        var callback = that.events[data.event][index];
                        callback.apply(that, data.args);
                    }
                }
            };

            that.socket.onopen = function() {
                ajaxify.throb.unsetError();

                logger.log('ws connection opened');

                $(that).trigger('open');
            };

            $(window).bind('beforeunload', function (event) {
                that.unloaded = true;
                that.socket.close();
            });

            that.socket.onclose = function() {
                logger.log('ws connection closed');

                if (!that.unloaded) {
                    ajaxify.throb.setError("Lost websocket connection, server is probably down.");

                    // TODO implement exponential backoff algo
                    setTimeout(function () {
                        that.internalInit();
                    }, 6000);
                }
            };

            that.socket.onerror = function(event) {
                logger.log('ws connection errored');

                ajaxify.throb.setError("Got websocket error: " + event.data);
            };
        },
        emit: function (event) {
            var that = this;

            var args = [].splice.call(arguments, 1);

            that.socket.send(JSON.stringify({
                'event': event,
                'args': args
            }));
        },
        on: function (event, callback) {
            var that = this;

            if (!(event in that.events)) {
                that.events[event] = [];
            }

            that.events[event].push(callback);
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Ws();
        }

        return instance;
    })();
});
