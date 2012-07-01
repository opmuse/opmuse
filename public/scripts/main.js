require(['jquery'], function($) {
    $('#library .track .play').click(function (event) {
        var url = $(this).attr('href');
        var player = $('#player').get(0);
        player.src = url;
        player.load();
        player.play();
        return false;
    });
});
