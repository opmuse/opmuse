define(['jquery', 'inheritance', 'ajaxify', 'ws', 'jquery.ui', 'jquery.nanoscroller', 'moment', 'bind', 'domReady!'],
    function($, inheritance, ajaxify, ws) {

    var Player = Class.extend({
        init: function (queue) {
            if (instance !== null) {
                throw Error('Only one instance of Player allowed!');
            }

            var that = this;

            this.queue = queue;

            this.player = $('#player').get(0);

            if (typeof this.player == 'undefined' || this.player === null) {
                return;
            }

            this.playerControls = $('#player-controls');
            this.playerProgress = $('#player-progress');
            this.trackTime = $('#track-time');
            this.trackUserAgent = $('#track-user-agent');
            this.trackDuration = $('#track-duration');
            this.queueDuration = $('#queue-duration');
            this.playButton = $('#play-button');
            this.pauseButton = $('#pause-button');
            this.nextButton = $('#next-button');
            this.playerTrack = $('#player-track');

            this.loaded = false;

            // if this is false it's an external player playing.
            this.usPlaying = false;

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
                that.setCurrent(track);
            });

            ws.on('queue.current_progress', function (progress) {
                that.setProgress(progress.seconds, progress.seconds_ahead);
            });

            ws.on('queue.start', function (track, user_agent) {
                that.setCurrent(track);

                that.queue.reload();

                that.setPlaying(user_agent);

                that.setProgress(0, 0);
            });

            ws.on('queue.end', function (track, user_agent) {
                that.setStopped();
            });

            ws.on('queue.progress', function (progress, track, user_agent) {
                if (that.currentTrack === null) {
                    that.currentTrack = track;
                }

                that.setPlaying(user_agent);

                that.setProgress(progress.seconds, progress.seconds_ahead);
            });

            ws.on('queue.next.none', function () {
                that.setCurrent(null);
                that.setProgress(0, 0);
                that.queue.reload();
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
                    that.usPlaying = true;
                    that.player.play();
                    that.playButton.hide();
                    that.pauseButton.show();
                }, 0);

                return false;
            });

            that.pauseButton.click(function() {
                if (that.usPlaying) {
                    that.usPlaying = false;
                    that.player.pause();
                    that.unload();
                    that.loaded = false;

                    that.pauseButton.hide();
                    that.playButton.show();
                }

                return false;
            });

            that.nextButton.click(function() {
                if (that.usPlaying) {
                    that.load();

                    setTimeout(function () {
                        that.player.play();
                    }, 0);
                }

                return false;
            });

            that.pauseButton.hide();

            that.internalInit();
        },
        setCurrent: function (track) {
            var that = this;

            that.currentTrack = track;

            var title = that.playerTrack.find('.title');

            if (track === null) {
                title.text('');
            } else {
                title.text(sprintf("%s - %s", track.artist.name, track.name));
            }
        },
        setProgress: function (seconds, seconds_ahead) {
            var that = this;

            var seconds_perc = seconds_ahead_perc = 0;

            if (that.currentTrack !== null) {
                var duration = that.currentTrack.duration;
                seconds_perc = ((seconds - seconds_ahead) / duration) * 100;
                seconds_ahead_perc = (seconds_ahead / duration) * 100;
            }

            that.playerProgress.find('.progress-bar.seconds').width(seconds_perc + '%');
            that.playerProgress.find('.progress-bar.ahead').width(seconds_ahead_perc + '%');

            that.trackTime.text(that.formatSeconds(seconds - seconds_ahead));
        },
        formatSeconds: function (seconds) {
            if (typeof seconds == 'undefined' || seconds === null) {
                seconds = 0;
            }

            var format = null;

            if (seconds >= 3600) {
                format = "HH:mm:ss";
            } else {
                format = "mm:ss";
            }

            return moment().hours(0).minutes(0).seconds(seconds).format(format);
        },
        setPlaying: function (user_agent) {
            var that = this;

            that.playButton.hide();
            that.pauseButton.show();

            if (!that.usPlaying) {
                that.pauseButton.addClass("disabled");
                that.nextButton.addClass("disabled");
            }

            that.trackUserAgent.text(user_agent).attr("title", user_agent);
        },
        setStopped: function () {
            var that = this;

            that.playButton.show();
            that.pauseButton.hide();

            that.pauseButton.removeClass("disabled");
            that.nextButton.removeClass("disabled");

            that.trackUserAgent.text('').attr("title", '');
        },
        internalInit: function () {
            $('#next-button, #play-button, #pause-button').unbind('click.ajaxify');
        },
        unload: function () {
            if (typeof this.player != 'undefined' && this.player !== null) {
                this.player.src = '/stream?dead=true';
            }
        },
        load: function () {
            if (typeof this.player != 'undefined' && this.player !== null) {
                // stupid cache bustin because firefox seems to refuse to not cache
                this.player.src = '/stream?b=' + Math.random();
            }
        }
    });

    var instance = null;

    var Queue = Class.extend({
        init: function () {
            if (instance !== null) {
                throw Error('Only one instance of Queue allowed!');
            }

            if ($('#queue').length == 0) {
                return;
            }

            var that = this;

            that.player = new Player(this);

            this.listUrl = '/queue/list';
            this.coverUrl = '/queue/cover';
            this.updateUrl = '/queue/update';

            $('#main').bind('ajaxifyInit', function (event) {
                that.internalInit();
            });

            $('#queue').bind('ajaxifyInit', function (event) {
                that.initNanoScroller();
            });

            that.internalInit();
            that.initNanoScroller();

            ws.on('queue.update', function () {
                that.reload();
            });
        },
        initNanoScroller: function () {
            $("#queue .nano").nanoScroller({
                alwaysVisible: true
            });

            $('#panel').unbind('panelFullscreen').bind('panelFullscreen', function (event) {
                $("#queue .nano").nanoScroller();
            });
        },
        internalInit: function () {
            var that = this;
            $('.queue.add')
                .unbind('click.queue')
                .bind('click.queue', function (event) {
                var url = $(this).attr('href');
                $.ajax(url);
                return false;
            }).unbind('click.ajaxify');

            $('#queue .remove')
                .unbind('click.queue')
                .bind("click.queue", function (event) {
                var url = $(this).attr('href');
                $.ajax(url);
                return false;
            }).unbind('click.ajaxify');

            $('#clear-queue, #clear-played-queue')
                .unbind('click.queue')
                .bind('click.queue', function (event) {
                var url = $(this).attr('href');
                $.ajax(url);
                return false;
            }).unbind('click.ajaxify');

            $('.open-stream').unbind('click.ajaxify');

            var items = null;

            $('#queue .tracks-wrapper .tracks').sortable({
                helper: 'clone',
                placeholder: 'placeholder',
                axis: 'y',
                items: 'li',
                handle: '.track-icon, .album-header-icon',
                start: function (event, ui) {
                    if ($(ui.item).hasClass("album")) {
                        items = $(ui.item).nextUntil('.album', '.track');
                    }
                },
                beforeStop: function (event, ui) {
                    if (items !== null) {
                        $(ui.item).after(items);
                        items = null;
                    }
                },
                update: function (event, ui) {
                    $.ajax(that.updateUrl, {
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        method: 'POST',
                        data: JSON.stringify({
                            queues: $(this).sortable('toArray', {attribute: 'data-queue-id'})
                        })
                    });
                }
            });

            that.player.trackDuration.text(
                that.player.formatSeconds(($("#queue").attr('data-queue_current_track-duration')))
            );

            that.player.queueDuration.text(
                that.player.formatSeconds(($("#queue").attr('data-queue_info-duration')))
            );
        },
        reload: function () {
            var that = this;

            $.ajax(this.listUrl, {
                success: function (data) {
                    ajaxify.setInDom("#queue", data);
                    ajaxify.load('#queue');
                    that.internalInit();
                }
            });

            $.ajax(this.coverUrl, {
                success: function (data) {
                    ajaxify.setInDom("#player-cover", data);
                    ajaxify.load('#player-cover');
                }
            });
        }
    });

    return (function() {
        if (instance === null) {
            instance = new Queue();
        }

        return instance;
    })();
});

