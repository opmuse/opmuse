require(['jquery'], function($) {
    var player = $('#player').get(0);

    var play = function () {
        // stupid cache bustin because firefox seems to refuse to not cache
        player.src = '/stream?b=' + Math.random();
        player.load();
    };

    var listUrl = '/playlist/list';

    $('.playlist.add').click(function (event) {
        var url = $(this).attr('href');
        $.ajax(url, {
            success: function (data) {
                $("#playlist").load(listUrl, {}, function () {
                    play();
                });
            }
        });
        return false;
    });

    $('#clear-playlist').click(function (event) {
        var url = $(this).attr('href');
        $.ajax(url, {
            success: function (data) {
                $("#playlist").empty();
            }
        });
        return false;
    });

    play();

    $("#playlist").load(listUrl);
});

