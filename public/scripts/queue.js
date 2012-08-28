define(['jquery', 'inheritance', 'bind', 'domReady!'], function($, inheritance) {

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

            $('.queue.add, .queue.add-album').click(function (event) {
                var url = $(this).attr('href');
                $.ajax(url, {
                    success: function (data) {
                        that.reload();
                    }
                });
                return false;
            });

            $('#queue .remove').live("click", function (event) {
                var url = $(this).attr('href');
                $.ajax(url, {
                    success: function (data) {
                        that.reload();
                    }
                });
                return false;
            });

            $('#clear-queue, #clear-played-queue').live('click', function (event) {
                var url = $(this).attr('href');
                $.ajax(url, {
                    success: function (data) {
                        that.reload();
                    }
                });
                return false;
            });

            that.reload();

            setInterval(this.reload.bind(this), 3 * 60 * 1000);
        },
        reload: function () {
            $.ajax(this.listUrl, {
                success: function (data) {
                    $("#queue").html(data);
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

