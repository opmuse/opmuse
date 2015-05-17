# Copyright 2012-2015 Mattias Fliesberg
#
# This file is part of opmuse.
#
# opmuse is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# opmuse is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with opmuse.  If not, see <http://www.gnu.org/licenses/>.

import os
from opmuse.library import Library, Artist
from . import setup_db, teardown_db
from nose.tools import with_setup


def library_start():
    library = Library(os.path.join(os.path.dirname(__file__), "../../sample_library"),
                      use_opmuse_txt=False)
    library.start()


@with_setup(setup_db, teardown_db)
class TestLibrary:
    def test_tracks(self):

        library_start()

        artists = self.session.query(Artist).order_by(Artist.name).all()

        assert len(artists) == 2

        assert artists[0].name == "opmuse"
        assert artists[0].albums[0].name == "opmuse"
        assert artists[0].albums[0].tracks[0].name == "opmuse"

        assert artists[1].name == "opmuse mp3"
        assert artists[1].albums[0].name == "opmuse mp3"
        assert artists[1].albums[0].tracks[0].name == "opmuse mp3"
