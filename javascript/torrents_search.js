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

function init() {
    $('#torrents_search .torrent-search-query')
        .off('keyup.search-query')
        .on('keyup.search-query', function(event) {
            if (event.keyCode == 13 && $(this).val() != '') {
                var value = $(this).val();
                var encodedValue = encodeURIComponent(value);

                ajaxify.setPage('/torrents/search?query=' + encodedValue);
            }

        });
}

$('#main').on('ajaxifyInit', function(event) {
    init();
});

init();
