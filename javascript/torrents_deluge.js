/*!
 * Copyright 2012-2015 Mattias Fliesberg
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

import $ from 'jquery';
import messages from 'opmuse/messages';
import ajaxify from 'opmuse/ajaxify';
import reloader from 'opmuse/reloader';

function init() {
    $('#torrents_deluge .torrent-import').click(function() {
        var button = $(this);
        var url = button.data('import-url');

        $.ajax(url, {
            success: function(data, textStatus, xhr) {
                reloader.load([".torrents_import"]);
                button.closest('tr').addClass("text-muted").find('.status span').text(data.status);
                button.attr('disabled', 'disabled');
            },
            error: function(xhr) {
                messages.danger('Failed to import torrent');
            }
        });
    });

    $('#torrents_deluge .mark-all-as-done').click(function() {
        var button = $(this);
        var url = button.attr('href');

        $.ajax(url, {
            success: function(data, textStatus, xhr) {
                ajaxify.setPage(document.location.href);
            },
            error: function(xhr) {
                messages.danger('Failed to mark all as done');
            }
        });

        return false;
    });

    var connectivity = $('#torrents_deluge .connectivity');

    if (connectivity.length > 0) {
        var url = connectivity.data('connectivity-url');

        $.ajax(url, {
            success: function(data, textStatus, xhr) {
                connectivity.removeClass('connecting');

                if (data.connected) {
                    connectivity.addClass('connected');
                } else {
                    connectivity.addClass('failed');
                }
            },
            error: function(xhr) {
                messages.danger('Failed to test connectivity');
            }
        });
    }
}

$('#main').on('ajaxifyInit', function(event) {
    init();
});

init();
