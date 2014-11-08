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

define([
        'jquery',
        'inheritance',
        'ajaxify',
        'ws',
        'messages',
        'Player',
        'modernizr',
        'jquery.ui',
        'jquery.nanoscroller',
        'moment',
        'domReady!'
    ], function ($, inheritance, ajaxify, ws, messages, Player) {

    'use strict';

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

            this.buttonSelectors = '#queue .remove, #clear-queue, #clear-played-queue, #shuffle-queue, .queue.add';

            $('#main').on('ajaxifyInit', function (event) {
                that.reload();
            });

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
            if (!$('#queue .nano').is('.has-scrollbar')) {
                $('#queue .nano').nanoScroller({
                    alwaysVisible: true
                });
            } else {
                $('#queue .nano').nanoScroller();
            }

            $('#panel').off('panelFullscreen').on('panelFullscreen', function (event) {
                $('#queue .nano').nanoScroller();
            });
        },
        internalInit: function () {
            var that = this;

            $(document).on('click.queue', that.buttonSelectors,
                function (event) {
                    var url = $(this).attr('href');
                    $.ajax(url);
                    return false;
                }
            );

            $(document).on('click', '#collapse-queue', function (event) {
                $('#queue').toggleClass('collapsed');
                $('#queue .nano').nanoScroller();
                return false;
            });

            that.reload();
        },
        reload: function () {
            var that = this;

            $(that.buttonSelectors + ', #collapse-queue , .open-stream').data('ajaxify', false);

            var items = null;

            $('#queue .tracks-wrapper .tracks').sortable({
                helper: 'clone',
                placeholder: 'placeholder',
                axis: 'y',
                items: 'li',
                handle: '.track-icon, .album-header-icon',
                start: function (event, ui) {
                    if ($(ui.item).hasClass('album')) {
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

            //that.player.trackDuration.text(
            //    that.player.formatSeconds(($("#queue").attr('data-queue_current_track-duration')))
            //);

            //that.player.queueDuration.text(
            //    that.player.formatSeconds(($("#queue").attr('data-queue_info-duration')))
            //);
        },
        reloadList: function () {
            var that = this;

            $.ajax(this.listUrl, {
                success: function (data) {
                    ajaxify.setInDom('#queue', data);
                    ajaxify.load('#queue');
                    that.reload();
                }
            });
        },
        reloadCover: function () {
            $.ajax(this.coverUrl, {
                success: function (data) {
                    ajaxify.setInDom('#player-cover', data);
                    ajaxify.load('#player-cover');
                }
            });
        }
    });

    return (function () {
        if (instance === null) {
            instance = new Queue();
        }

        return instance;
    })();
});
