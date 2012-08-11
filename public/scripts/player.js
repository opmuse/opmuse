define(['jquery', 'inheritance', 'playlist'], function($, inheritance, playlist) {
    var instance = null;

    var Player = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Player allowed!');
            }

            var that = this;

            this.player = $('#player').get(0);
            this.player_controls = $('#player-controls');
            this.play_button = $('#play-button');
            this.pause_button = $('#pause-button');

            // TODO replace with requirejs domready plugin
            $(function() {

                $(that.player).bind('playing', function (event) {
                    playlist.reload();
                });

                $(that.player).bind('ended', function (event) {
                    that.load();
                    that.player.play();
                });

                that.play_button.click(function() {
                    that.player.play();
                    that.play_button.hide();
                    that.pause_button.show();
                });

                that.pause_button.click(function() {
                    that.player.pause();
                    that.pause_button.hide();
                    that.play_button.show();
                });

                that.pause_button.hide();
                that.player_controls.show();

                that.load();
            });
        },
        load: function () {
            if (typeof this.player != 'undefined' && this.player !== null) {
                // stupid cache bustin because firefox seems to refuse to not cache
                this.player.src = '/stream/one?b=' + Math.random();
                this.player.load();
            }
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Player();
        }

        return instance;
    })();

});

