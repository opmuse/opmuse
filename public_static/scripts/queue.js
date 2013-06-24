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
                that.setCurrent(track);
            });

            ws.on('queue.current_progress', function (progress) {
                that.setProgress(progress.seconds, progress.seconds_ahead);
            });

            ws.on('queue.start', function (track) {
                that.setCurrent(track);

                that.queue.reload();

                that.setProgress(0, 0);
            });

            ws.on('queue.progress', function (progress, track) {
                if (that.currentTrack === null) {
                    that.currentTrack = track;
                }

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

            that.playerProgress.find('.bar.seconds').width(seconds_perc + '%');

            that.playerProgress.find('.bar.ahead').width(seconds_ahead_perc + '%');

            var actual_seconds = seconds - seconds_ahead;

            var format = null;

            if (actual_seconds >= 3600) {
                format = "HH:mm:ss";
            } else {
                format = "mm:ss";
            }

            var time = '';

            if (actual_seconds > 0) {
                time = moment().hours(0).minutes(0).seconds(actual_seconds).format(format);
            }

            that.playerTrack.find('.time').text(time);
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
        },
        reload: function () {
            var that = this;

            $.ajax(this.listUrl, {
                success: function (data) {
                    $("#queue").html(data);
                    ajaxify.load('#queue');
                    that.internalInit();
                }
            });

            $.ajax(this.coverUrl, {
                success: function (data) {
                    $("#player-cover").html(data);
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
