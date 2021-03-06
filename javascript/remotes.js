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
import ws from 'opmuse/ws';
import ajaxify from 'opmuse/ajaxify';
import reloader from 'opmuse/reloader';

class Remotes {
    constructor() {
        var that = this;

        ws.on('remotes.artist.fetched', function(id, album_ids, track_ids) {
            var selectors = that.getArtistSelectors(id);

            // because artist data is shown on album page we
            // want to update those too, in case the user is on said page.
            for (var index in album_ids) {
                var album_id = album_ids[index];
                selectors = selectors.concat(that.getAlbumSelectors(album_id));
            }

            for (var index in track_ids) {
                var track_id = track_ids[index];
                selectors = selectors.concat(that.getTrackSelectors(track_id));
            }

            reloader.load(selectors);
        });

        ws.on('remotes.album.fetched', function(id, track_ids) {
            var selectors = that.getAlbumSelectors(id);

            for (var index in track_ids) {
                var track_id = track_ids[index];
                selectors = selectors.concat(that.getTrackSelectors(track_id));
            }

            reloader.load(selectors);
        });

        ws.on('remotes.track.fetched', function(id) {
            var selectors = that.getTrackSelectors(id);
            reloader.load(selectors);
        });

        ws.on('remotes.tag.fetched', function(tag_name) {
            var selectors = that.getTagSelectors(tag_name);
            reloader.load(selectors);
        });
    }
    getTrackSelectors(id) {
        return ['.remotes_track_head_' + id, '.remotes_track_nav_' + id];
    }
    getArtistSelectors(id) {
        return ['.remotes_artist_head_' + id, '.remotes_artist_nav_' + id];
    }
    getAlbumSelectors(id) {
        return ['.remotes_album_head_' + id, '.remotes_album_nav_' + id];
    }
    getTagSelectors(tag_name) {
        return ['[data-remotes-tag="' + tag_name + '"]'];
    }
}

export default new Remotes();
