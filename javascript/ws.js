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
import logger from 'opmuse/logger';
import ajaxify from 'opmuse/ajaxify';
import messages from 'opmuse/messages';
import 'npm-modernizr';

class Ws {
    constructor() {
        var that = this;

        that.checkCapabilities();

        that.events = {};

        if (!opmuseGlobals.authenticated) {
            return;
        }

        var host = null;

        if (opmuseGlobals.ws_port !== null) {
            host = sprintf('%s:%d', document.location.hostname, opmuseGlobals.ws_port);
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
    }
    checkCapabilities() {
        if (!Modernizr.websockets) {
            this.error('Your browser is missing WebSockets support, things will not work as expected.');
        }
    }
    error(text) {
        messages.danger(text);
        ajaxify.throb.setError(text);
    }
    unsetError() {
        ajaxify.throb.unsetError();
    }
    internalInit() {
        var that = this;

        that.socket = new WebSocket(that.url);

        var errTimeout = 1000;

        var times = 1;

        var errHandler = function() {
            if (that.socket.readyState === WebSocket.CONNECTING) {
                logger.log(sprintf('ws connecting%s', Array(times).join('.')));

                times += 1;

                setTimeout(errHandler, errTimeout);
            } else if (that.socket.readyState !== WebSocket.OPEN) {
                that.error('Couldn\'t establish websocket connection, might be firewall issues.');
            }
        };

        setTimeout(errHandler, errTimeout);

        that.socket.onmessage = function(event) {
            var data = JSON.parse(event.data);

            logger.log(sprintf('ws got event %s with args %s', data.event, JSON.stringify(data.args)));

            if (data.event in that.events) {
                for (var index in that.events[data.event]) {
                    var callback = that.events[data.event][index];

                    var eventObj = {
                        event: data.event
                    };

                    callback.apply(eventObj, data.args);
                }
            }
        };

        that.socket.onopen = function() {
            that.unsetError();

            logger.log('ws connection opened');

            $(that).trigger('open');
        };

        $(window).on('beforeunload', function(event) {
            that.unloaded = true;
            that.socket.close();
        });

        that.socket.onclose = function() {
            logger.log('ws connection closed');

            if (!that.unloaded) {
                that.error('Lost websocket connection, server is probably down.');

                // TODO implement exponential backoff algo
                setTimeout(function() {
                    that.internalInit();
                }, 6000);
            }
        };

        that.socket.onerror = function(event) {
            logger.log('ws connection errored');

            that.error('Got websocket error: ' + event.data);
        };
    }
    emit(event) {
        var that = this;

        var args = [].splice.call(arguments, 1);

        that.socket.send(JSON.stringify({
            'event': event,
            'args': args
        }));
    }
    on(event, callback) {
        var that = this;

        var events;

        if (event instanceof Array) {
            events = event;
        } else {
            events = [event];
        }

        for (var index in events) {
            event = events[index];

            if (!(event in that.events)) {
                that.events[event] = [];
            }

            that.events[event].push(callback);
        }
    }
}

export default new Ws();
