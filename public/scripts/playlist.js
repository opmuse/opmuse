define(['jquery', 'inheritance'], function($, inheritance) {

    var instance = null;

    var Playlist = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Playlist allowed!');
            }

            if ($('#playlist').length == 0) {
                return;
            }

            var that = this;

            this.listUrl = '/playlist/list';

            $(function() {
                $('.playlist.add, .playlist.add-album').click(function (event) {
                    var url = $(this).attr('href');
                    $.ajax(url, {
                        success: function (data) {
                            that.reload();
                        }
                    });
                    return false;
                });

                $('#playlist .remove').live("click", function (event) {
                    var url = $(this).attr('href');
                    $.ajax(url, {
                        success: function (data) {
                            that.reload();
                        }
                    });
                    return false;
                });

                $('#clear-playlist').click(function (event) {
                    var url = $(this).attr('href');
                    $.ajax(url, {
                        success: function (data) {
                            $("#playlist-tracks").empty();
                        }
                    });
                    return false;
                });

                that.reload();
            });
        },
        reload: function () {
            $("#playlist-tracks").load(this.listUrl, {});
        },
    });

    return (function() {
        if (instance === null) {
            instance = new Playlist();
        }

        return instance;
    })();
});

