/*!
 * Copyright 2012-2014 Mattias Fliesberg
 *
 * This file is part of opmuse.
 *
 * opmuse is free software: you can redistribute it and/or modify
 * it under the terms of the GNU Affero General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 *
 * opmuse is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with opmuse.  If not, see <http://www.gnu.org/licenses/>.
 */

define(['jquery', 'inheritance', 'ajaxify', 'ws', 'jquery.ui', 'jquery.nanoscroller', 'moment', 'bind', 'domReady!'],
    function($, inheritance, ajaxify, ws) {

    "use strict";

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
            this.trackDuration = $('#track-duration');
            this.queueDuration = $('#queue-duration');
            this.playButton = $('#play-button');
            this.pauseButton = $('#pause-button');
            this.nextButton = $('#next-button');
            this.stopButton = $('#stop-button');
            this.playerTrack = $('#player-track');

            this.loaded = false;

            // if this is false it's an external player playing.
            this.usPlaying = false;

            // this is true if someone is using the stream
            this.playing = false;

            that.currentTrack = null;

            $(window).on('beforeunload', function (event) {
                if (!that.player.paused) {
                    return false;
                }
            });

            $(ws).on('open', function () {
                ws.emit('queue.open');
            });

            ws.on('queue.current_track', function (track) {
                that.setCurrent(track);
            });

            ws.on('queue.current_progress', function (progress) {
                that.setProgress(progress.seconds, progress.seconds_ahead);
            });

            ws.on('queue.reset', function (track, user_agent) {
                that.setCurrent(null);
                that.setProgress(0, 0);
            });

            ws.on('queue.start', function (track, user_agent, format) {
                that.setCurrent(track);

                that.queue.reloadList();
                that.queue.reloadCover();

                that.setPlaying(user_agent, format);
            });

            ws.on('queue.end', function (track, user_agent) {
                that.setStopped();
            });

            ws.on('queue.progress', function (progress, track, user_agent, format) {
                if (that.currentTrack === null) {
                    that.currentTrack = track;
                }

                that.setPlaying(user_agent, format);

                that.setProgress(progress.seconds, progress.seconds_ahead);
            });

            ws.on('queue.next.none', function () {
                that.setCurrent(null);
                that.setProgress(0, 0);
                that.queue.reloadList();
                that.queue.reloadCover();
            });

            $(that.player).on('ended', function (event) {
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

            that.stopButton.click(function() {
                if (that.usPlaying) {
                    that.usPlaying = false;
                    that.player.pause();
                    that.unload();
                    that.loaded = false;

                    that.pauseButton.hide();
                    that.playButton.show();
                }

                if (that.usPlaying || !that.playing) {
                    var url = $(this).attr('href');

                    // we need to wait some until the <audio> player has closed the
                    // connection or we might get a queue.progress event after we've
                    // done this...
                    setTimeout(function () {
                        $.ajax(url);
                    }, 500);
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

            var seconds_perc = 0;
            var seconds_ahead_perc = 0;

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
        setPlaying: function (user_agent, format) {
            var that = this;

            that.playing = true;

            that.playButton.hide();
            that.pauseButton.show();

            if (!that.usPlaying) {
                that.pauseButton.addClass("disabled");
                that.nextButton.addClass("disabled");
                that.stopButton.addClass("disabled");
            }
        },
        setStopped: function () {
            var that = this;

            that.playing = false;

            that.playButton.show();
            that.pauseButton.hide();

            that.pauseButton.removeClass("disabled");
            that.nextButton.removeClass("disabled");
            that.stopButton.removeClass("disabled");
        },
        internalInit: function () {
            $('#next-button, #play-button, #pause-button').data('ajaxify', false);
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

            $('#queue').on('ajaxifyInit', function (event) {
                that.initNanoScroller();
            });

            that.internalInit();
            that.initNanoScroller();

            ws.on('queue.update', function () {
                that.reloadList();
            });
        },
        initNanoScroller: function () {
            $("#queue .nano").nanoScroller({
                alwaysVisible: true
            });

            $('#panel').off('panelFullscreen').on('panelFullscreen', function (event) {
                $("#queue .nano").nanoScroller();
            });
        },
        internalInit: function () {
            var that = this;

            $('.queue.add')
                .off('click.queue')
                .on('click.queue', function (event) {
                var url = $(this).attr('href');
                $.ajax(url);
                return false;
            });

            $('#queue .remove')
                .off('click.queue')
                .on("click.queue", function (event) {
                var url = $(this).attr('href');
                $.ajax(url);
                return false;
            });

            $('#collapse-queue')
                .off('click.queue')
                .on('click.queue', function (event) {
                $('#queue').toggleClass('collapsed');
                $("#queue .nano").nanoScroller();
                return false;
            });

            $('#clear-queue, #clear-played-queue, #shuffle-queue')
                .off('click.queue')
                .on('click.queue', function (event) {
                var url = $(this).attr('href');
                $.ajax(url);
                return false;
            });

            $('.open-stream').data('ajaxify', false);

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
                        if ($(ui.item).prev('.album').length > 0) {
                            $(ui.item).nextUntil('.album', '.track').last().after(items);
                        } else {
                            $(ui.item).after(items);
                        }

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
        reloadList: function () {
            var that = this;

            $.ajax(this.listUrl, {
                success: function (data) {
                    ajaxify.setInDom("#queue", data);
                    ajaxify.load('#queue');
                    that.internalInit();
                }
            });
        },
        reloadCover: function () {
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

