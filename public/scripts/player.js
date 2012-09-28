define(['jquery', 'inheritance', 'queue', 'domReady!'], function($, inheritance, queue) {
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
            this.next_button = $('#next-button');

            $(that.player).bind('playing', function (event) {
                queue.reload();
            });

            $(that.player).bind('ended', function (event) {
                that.load();
                that.player.play();
            });

            that.play_button.click(function() {
                that.player.play();
                that.play_button.hide();
                that.pause_button.show();

                return false;
            });

            that.pause_button.click(function() {
                that.player.pause();
                that.pause_button.hide();
                that.play_button.show();

                return false;
            });

            that.next_button.click(function() {
                var paused = that.player.paused;
                that.load();

                if (paused === false) {
                    that.player.play();
                }

                return false;
            });

            that.pause_button.hide();
            that.player_controls.show();

            that.load();
        },
        load: function () {
            if (typeof this.player != 'undefined' && this.player !== null) {
                // stupid cache bustin because firefox seems to refuse to not cache
                this.player.src = '/stream?b=' + Math.random();
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

