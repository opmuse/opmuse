# Copyright 2012-2014 Mattias Fliesberg
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

from datetime import datetime, timedelta


def pretty_date(time, ago="ago"):
    now = datetime.now()

    if time is None:
        time = 0
    elif type(time) is str:
        time = int(time)

    if type(time) is int or type(time) is float:
        if time > 3600 * 24 * 365 * 10:
            diff = now - datetime.fromtimestamp(time)
        else:
            diff = timedelta(seconds=time)
    elif isinstance(time, datetime):
        diff = now - time
    else:
        raise ValueError("Unsupported time value.")

    second_diff = diff.seconds
    day_diff = diff.days

    if day_diff < 0:
        return ''

    if len(ago) > 0:
        ago = " %s" % ago

    if day_diff == 0:
        if second_diff < 60:
            return "%d seconds%s" % (second_diff, ago)
        elif second_diff < 120:
            return "a minute%s" % ago
        elif second_diff < 3600:
            return "%d minutes%s" % ((second_diff / 60), ago)
        elif second_diff < 7200:
            return "an hour%s" % ago
        elif second_diff < 86400:
            return "%d hours%s" % ((second_diff / 3600), ago)
    else:
        if day_diff == 1:
            return "1 day%s" % ago
        elif day_diff < 7:
            return "%d days%s" % (day_diff, ago)
        elif day_diff < 31:
            return "%d weeks%s" % ((day_diff / 7), ago)
        elif day_diff < 365:
            return "%d months%s" % ((day_diff / 30), ago)

    return "%d years%s" % ((day_diff / 365), ago)
