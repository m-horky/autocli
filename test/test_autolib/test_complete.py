import pathlib
import json

import autolib

_SPECIFICATION_FILE = pathlib.Path(__file__).parent / "specification.json"
with _SPECIFICATION_FILE.open("r") as f:
    _SPECIFICATION = json.load(f)

AT = autolib.AutoTool(specification=_SPECIFICATION)


class TestPath:
    def test_empty(self):
        expected = ("dns", "status")
        actual = AT.complete([""])
        assert expected == actual

    def test_full(self):
        expected = ("status",)
        actual = AT.complete(["status"])
        assert expected == actual
    
    def test_full_completed(self):
        expected = tuple()
        actual = AT.complete(["status", ""])
        assert expected == actual

    def test_children(self):
        expected = ("domain=", "domains")
        actual = AT.complete(["dns", ""])
        assert expected == actual


class TestPathWithVariable:
    def test_as_current_argument(self):
        expected = ("domain=", )
        actual = AT.complete(["dns", "domain="])
        assert expected == actual

    def test_as_current_argument_with_value(self):
        expected = ("domain=example.org", )
        actual = AT.complete(["dns", "domain=example.org"])
        assert expected == actual

    def test_as_previous_argument_with_value(self):
        expected = ("a",)
        actual = AT.complete(["dns", "domain=example.org", "a"])
        assert expected == actual


class TestMethod:
    def test_only_one_method_flag_present(self):
        expected = ("get", )
        actual = AT.complete(["dns", "domains", "-X", ""])
        assert expected == actual
    
    def test_only_one_method_dash(self):
        expected = ("-X", )
        actual = AT.complete(["dns", "domains", "-"])
        assert expected == actual


class TestHeader:
    def test_no_method_specified(self):
        expected = tuple()
        actual = AT.complete(["dns", "domains", "-H"])
        assert expected == actual

    def test_one_header_available(self):
        expected = ("Authorization", )
        actual = AT.complete(["dns", "domains", "-X", "GET", "-H"])
        assert expected == actual
    
    def test_valud_not_suggested(self):
        expected = tuple()
        actual = AT.complete(["dns", "domains", "-X", "GET", "-H", "Authorization", ""])
        assert expected == actual
        assert False
    

class TestQuery:
    def test_no_method_specified(self):
        expected = tuple()
        actual = AT.complete(["dns", "domain=example.org", "a", "-Q", ""])
        assert expected == actual

    def test_available(self):
        expected = ("name", "name2")
        actual = AT.complete(["dns", "domain=example.org", "a", "-X", "POST", "-Q"])
        assert expected == actual

    def test_one_filled_in(self):
        expected = ("name2", )
        actual = AT.complete(["dns", "domain=example.org", "a", "-X", "POST", "-Q", "name", "value", "-Q"])
        assert expected == actual
