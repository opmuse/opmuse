define(['jquery', 'inheritance', 'ajaxify', 'ws', 'jquery.nanoscroller', 'bind', 'domReady!'],
    function($, inheritance, ajaxify, ws) {

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

            $('#queue').bind('ajaxifyInit', function (event) {
                that.initNanoScroller();
            });

            that.internalInit();
            that.initNanoScroller();

            ws.on('queue.update', function () {
                that.reload();
            });
        },
        initNanoScroller: function () {
            $("#queue .nano").nanoScroller({
                alwaysVisible: true
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
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Queue();
        }

        return instance;
    })();
});

