require(['jquery'], function($) {
    var player = $('#player').get(0);
    var player_controls = $('#player-controls');
    var play_button = $('#play-button');
    var pause_button = $('#pause-button');

    $(function() {
        play_button.click(function() {
            player.play();
            play_button.hide();
            pause_button.show();
        });

        pause_button.click(function() {
            player.pause();
            pause_button.hide();
            play_button.show();
        });

        pause_button.hide();
        player_controls.show();
    });

});

