# Copyright 2012-2013 Mattias Fliesberg
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

from datetime import datetime


def pretty_date(time):
    now = datetime.now()

    if time is None:
        time = 0
    elif type(time) is str:
        time = int(time)

    if type(time) is int or type(time) is float:
        diff = now - datetime.fromtimestamp(time)
    elif isinstance(time, datetime):
        diff = now - time
    else:
        raise ValueError("Unsupported time value.")

    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if day_diff == 0:
        if second_diff < 10:
            return "just now"
        elif second_diff < 60:
            return "%d seconds ago" % second_diff
        elif second_diff < 120:
            return "a minute ago"
        elif second_diff < 3600:
            return "%d minutes ago" % (second_diff / 60)
        elif second_diff < 7200:
            return "an hour ago"
        elif second_diff < 86400:
            return "%d hours ago" % (second_diff / 3600)
    else:
        if day_diff == 1:
            return "1 day ago"
        elif day_diff < 7:
            return "%d days ago" % day_diff
        elif day_diff < 31:
            return "%d weeks ago" % (day_diff / 7)
        elif day_diff < 365:
            return "%d months ago" % (day_diff / 30)

    return "%d years ago" % (day_diff / 365)
