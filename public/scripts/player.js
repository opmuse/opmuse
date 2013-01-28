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
            this.playerTrack = $('#player-track');

            this.loaded = false;

            that.currentTrackDuration = 0;

            $(window).bind('beforeunload', function (event) {
                if (!that.player.paused) {
                    return false;
                }
            });

            $(that.player).bind('playing', function (event) {
                queue.reload(function (data) {
                    var track = queue.getCurrentTrack();
                    that.playerTrack.text(track.title);
                    that.currentTrackDuration = track.duration;
                });
                that.setProgressActive(true);
            });

            $(that.player).bind('pause', function (event) {
                that.setProgressActive(false);
            });

            $(that.player).bind('ended', function (event) {
                that.setProgress(0);
                that.load();

                setTimeout(function () {
                    that.player.play();
                }, 0);
            });

            $(that.player).bind('timeupdate', function (event) {
                var prog = (this.currentTime / (that.currentTrackDuration)) * 100;
                that.setProgress(prog);
            });

            that.playButton.click(function() {
                if (!that.loaded) {
                    that.load();
                    that.loaded = true;
                }

                setTimeout(function () {
                    that.player.play();
                    that.playButton.hide();
                    that.pauseButton.show();
                }, 0);

                return false;
            });

            that.pauseButton.click(function() {
                that.player.pause();
                that.pauseButton.hide();
                that.playButton.show();

                return false;
            });

            that.nextButton.click(function() {
                that.load();

                setTimeout(function () {
                    that.player.play();
                }, 0);

                return false;
            });

            that.pauseButton.hide();

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
            $('#next-button, #play-button, #pause-button').unbind('click.ajaxify');
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

