require(['jquery'], function($) {
    if ($('#player').length == 0) {
        return;
    }

    var player = $('#player').get(0);

    var play = function () {
        if (typeof player != 'undefined' && player !== null) {
            // stupid cache bustin because firefox seems to refuse to not cache
            player.src = '/stream?b=' + Math.random();
            player.load();
        }
    };

    var listUrl = '/playlist/list';

    $('.playlist.add, .playlist.add-album').click(function (event) {
        var url = $(this).attr('href');
        $.ajax(url, {
            success: function (data) {
                $("#playlist-tracks").load(listUrl, {}, function () {
                    play();
                });
            }
        });
        return false;
    });

    $('#playlist .remove').live("click", function (event) {
        var url = $(this).attr('href');
        $.ajax(url, {
            success: function (data) {
                $("#playlist-tracks").load(listUrl);
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

    play();

    $("#playlist-tracks").load(listUrl);
});

