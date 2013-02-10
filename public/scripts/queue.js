define(['jquery', 'inheritance', 'ajaxify', 'ws', 'bind', 'domReady!'], function($, inheritance, ajaxify, ws) {

    var instance = null;

    var Queue = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Queue allowed!');
            }

            if ($('#queue').length == 0) {
                return;
            }

            var that = this;

            this.listUrl = '/queue/list';

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();

            ws.on('queue.update', function () {
                that.reload();
            });
        },
        internalInit: function () {
            var that = this;
            $('.queue.add')
                .unbind('click.queue')
                .bind('click.queue', function (event) {
                var url = $(this).attr('href');
                $.ajax(url);
                return false;
            }).unbind('click.ajaxify');

            $('#queue .remove')
                .unbind('click.queue')
                .bind("click.queue", function (event) {
                var url = $(this).attr('href');
                $.ajax(url);
                return false;
            }).unbind('click.ajaxify');

            $('#clear-queue, #clear-played-queue')
                .unbind('click.queue')
                .bind('click.queue', function (event) {
                var url = $(this).attr('href');
                $.ajax(url);
                return false;
            }).unbind('click.ajaxify');

            $('.open-stream').unbind('click.ajaxify');
        },
        reload: function (successCallback) {
            var that = this;

            $.ajax(this.listUrl, {
                success: function (data) {
                    $("#queue").html(data);
                    ajaxify.load('#queue');
                    that.internalInit();

                    if (typeof successCallback != 'undefined' && successCallback !== null) {
                        successCallback(data);
                    }
                }
            });
        },
        getCurrentTrack: function () {
            var track = $("#queue .track.playing");

            return {
                'duration': track.data('track-duration'),
                'title': track.data('track-title'),
            };
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Queue();
        }

        return instance;
    })();
});

