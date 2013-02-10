define(['jquery', 'inheritance', 'sprintf', 'bind', 'domReady!'], function($, inheritance) {

    var instance = null;

    var Ws = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Ws allowed!');
            }

            var that = this;

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

            that.events = {};

            that.internalInit();
        },
        internalInit: function () {
            var that = this;

            that.socket = new WebSocket(that.url);

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
                $(that).trigger('open');
            };

            $(window).bind('beforeunload', function (event) {
                that.unloaded = true;
                that.socket.close();
            });

            that.socket.onclose = function() {
                if (!that.unloaded) {
                    // TODO implement exponential backoff algo
                    setTimeout(function () {
                        that.internalInit();
                    }, 2000);
                }
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
