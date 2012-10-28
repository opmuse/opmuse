define(['jquery', 'inheritance', 'queue', 'ajaxify', 'domReady!'], function($, inheritance, queue, ajaxify) {
    var instance = null;

    var Player = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Player allowed!');
            }

            var that = this;

            this.player = $('#player').get(0);
            this.playerControls = $('#player-controls');
            this.playerProgress = $('#player-progress');
            this.playButton = $('#play-button');
            this.pauseButton = $('#pause-button');
            this.nextButton = $('#next-button');

            that.currentTrackDuration = 0;

            $(that.player).bind('playing', function (event) {
                queue.reload(function (data) {
                    that.currentTrackDuration = queue.getCurrentTrackDuration();
                });
                that.setProgressActive(true);
            });

            $(that.player).bind('pause', function (event) {
                that.setProgressActive(false);
            });

            $(that.player).bind('ended', function (event) {
                that.setProgress(0);
                that.load();
                that.player.play();
            });

            $(that.player).bind('timeupdate', function (event) {
                var prog = (this.currentTime / (that.currentTrackDuration)) * 100;
                that.setProgress(prog);
            });

            that.playButton.click(function() {
                that.player.play();
                that.playButton.hide();
                that.pauseButton.show();

                return false;
            });

            that.pauseButton.click(function() {
                that.player.pause();
                that.pauseButton.hide();
                that.playButton.show();

                return false;
            });

            that.nextButton.click(function() {
                var paused = that.player.paused;
                that.load();

                if (paused === false) {
                    that.player.play();
                }

                return false;
            });

            that.pauseButton.hide();
            that.playerControls.show();

            that.load();

            $('#footer').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            that.internalInit();
        },
        setProgressActive: function (active) {
            var progress = this.playerProgress.find('.progress');

            if (active) {
                progress.addClass('active');
            } else {
                progress.removeClass('active');
            }
        },
        setProgress: function (prog) {
            this.playerProgress.find('.bar').width(prog + '%');
        },
        internalInit: function () {
            $('.open-stream').unbind('click.ajaxify');
        },
        load: function () {
            if (typeof this.player != 'undefined' && this.player !== null) {
                // stupid cache bustin because firefox seems to refuse to not cache
                this.player.src = '/stream?b=' + Math.random();
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

