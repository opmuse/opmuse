define(['jquery', 'inheritance', 'queue', 'ajaxify', 'ws', 'moment', 'sprintf', 'domReady!'],
    function($, inheritance, queue, ajaxify, ws, moment) {
    var instance = null;

    var Player = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Player allowed!');
            }

            var that = this;

            this.player = $('#player').get(0);

            if (typeof this.player == 'undefined' || this.player === null) {
                return;
            }

            this.playerControls = $('#player-controls');
            this.playerProgress = $('#player-progress');
            this.playButton = $('#play-button');
            this.pauseButton = $('#pause-button');
            this.nextButton = $('#next-button');
            this.playerTrack = $('#player-track');

            this.loaded = false;

            that.currentTrack = null;

            $(window).bind('beforeunload', function (event) {
                if (!that.player.paused) {
                    return false;
                }
            });

            $(ws).bind('open', function () {
                ws.emit('queue.open');
            });

            ws.on('queue.current_track', function (track) {
                that.setPlaying(track);
            });

            ws.on('queue.current_progress', function (progress) {
                that.setProgress(progress.seconds, progress.seconds_ahead);
            });

            ws.on('queue.start', function (track) {
                that.setPlaying(track);
                that.playerTrack.find('.title').text(sprintf("%s - %s", track.artist.name, track.name));

                queue.reload();

                that.setProgress(0, 0);
            });

            ws.on('queue.progress', function (progress, track) {
                if (that.currentTrack === null) {
                    that.currentTrack = track;
                }

                that.setProgress(progress.seconds, progress.seconds_ahead);
            });

            $(that.player).bind('ended', function (event) {
                that.setProgress(0, 0);
                that.load();

                setTimeout(function () {
                    that.player.play();
                }, 0);
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
        setPlaying: function (track) {
            var that = this;
            that.currentTrack = track;
            that.playerTrack.find('.title').text(sprintf("%s - %s", track.artist.name, track.name));
        },
        setProgress: function (seconds, seconds_ahead) {
            var that = this;

            var duration = that.currentTrack.duration;

            that.playerProgress.find('.bar.seconds').width(
                (((seconds - seconds_ahead) / duration) * 100) + '%'
            );

            that.playerProgress.find('.bar.ahead').width(
                ((seconds_ahead / duration) * 100) + '%'
            );

            var actual_seconds = seconds - seconds_ahead;

            var format = null;

            if (actual_seconds >= 3600) {
                format = "HH:mm:ss";
            } else {
                format = "mm:ss";
            }

            that.playerTrack.find('.time').text(
                moment().hours(0).minutes(0).seconds(actual_seconds).format(format)
            );
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

