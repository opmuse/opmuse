define(['jquery', 'inheritance', 'ajaxify', 'bind', 'domReady!'], function($, inheritance, ajaxify) {

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

            $('body').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();

            that.reload();

            setInterval(this.reload.bind(this), 3 * 60 * 1000);

            $("#top-right").bind("layoutResize", function (event) {
                $("#queue > .tracks").hide();
                var margin = $("#queue").outerHeight() + 10;
                $("#queue > .tracks").height(
                    $("#top-right").height() - margin
                ).show();
            });
        },
        internalInit: function () {
            var that = this;
            $('.queue.add, .queue.add-album')
                .unbind('click.queue')
                .bind('click.queue', function (event) {
                var url = $(this).attr('href');
                $.ajax(url, {
                    success: function (data) {
                        that.reload();
                    }
                });
                return false;
            }).unbind('click.ajaxify');

            $('#queue .remove')
                .unbind('click.queue')
                .bind("click.queue", function (event) {
                var url = $(this).attr('href');
                $.ajax(url, {
                    success: function (data) {
                        that.reload();
                    }
                });
                return false;
            }).unbind('click.ajaxify');

            $('#clear-queue, #clear-played-queue')
                .unbind('click.queue')
                .bind('click.queue', function (event) {
                var url = $(this).attr('href');
                $.ajax(url, {
                    success: function (data) {
                        that.reload();
                    }
                });
                return false;
            }).unbind('click.ajaxify');
        },
        reload: function () {
            var that = this;
            $.ajax(this.listUrl, {
                success: function (data) {
                    $("#queue").html(data);
                    ajaxify.internalInit();
                    that.internalInit();
                }
            });
        },
    });

    return (function() {
        if (instance === null) {
            instance = new Queue();
        }

        return instance;
    })();
});

