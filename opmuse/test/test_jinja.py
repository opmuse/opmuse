import locale
from opmuse.jinja import (show_ws, format_bytes, format_number, nl2p,
                          format_seconds_alt, format_seconds)


class TestJinja:
    def test_show_ws(self):
        assert show_ws(' artist name') == "␣artist name"
        assert show_ws(' artist name ') == "␣artist name␣"
        assert show_ws('artist name ') == "artist name␣"
        assert show_ws('artist name   ') == "artist name␣␣␣"

    def test_format_bytes(self):
        assert format_bytes(2000) == "1.95 KB"
        assert format_bytes(2000 * 1024) == "1.95 MB"
        assert format_bytes(2000 * pow(1024, 2)) == "1.95 GB"
        assert format_bytes(2000 * pow(1024, 3)) == "1.95 TB"
        assert format_bytes(2000, 4) == "1.9531 KB"

    def test_format_number(self):
        locale.setlocale(locale.LC_ALL, 'en_US.utf8')
        assert format_number(1000000) == "1,000,000"

    def test_nl2p(self):
        assert nl2p("hi\nmy\nname is john") == "<p>hi</p><p>my</p><p>name is john</p>"

    def test_format_seconds_alt(self):
        assert format_seconds_alt(30) == "30s"
        assert format_seconds_alt(1000) == "16m 40s"
        assert format_seconds_alt(5000) == "1h 23m 20s"

    def test_format_seconds(self):
        assert format_seconds(30) == "00:30"
        assert format_seconds(1000) == "16:40"
        assert format_seconds(5000) == "01:23:20"
