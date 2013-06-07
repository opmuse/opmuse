define(['jquery', 'inheritance', 'ajaxify', 'ws', 'jquery.ui', 'jquery.nanoscroller', 'bind', 'domReady!'],
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
            this.updateUrl = '/queue/update';

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

            $('#panel').unbind('panelFullscreen').bind('panelFullscreen', function (event) {
                $("#queue .nano").nanoScroller();
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

            var items = null;

            $('#queue .tracks-wrapper .tracks').sortable({
                helper: 'clone',
                placeholder: 'placeholder',
                axis: 'y',
                items: 'li',
                handle: '.track-icon, .album-header-icon',
                start: function (event, ui) {
                    if ($(ui.item).hasClass("album")) {
                        items = $(ui.item).nextUntil('.album', '.track');
                    }
                },
                beforeStop: function (event, ui) {
                    if (items !== null) {
                        $(ui.item).after(items);
                        items = null;
                    }
                },
                update: function (event, ui) {
                    $.ajax(that.updateUrl, {
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        method: 'POST',
                        data: JSON.stringify({
                            queues: $(this).sortable('toArray', {attribute: 'data-queue-id'})
                        })
                    });
                }
            });
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

