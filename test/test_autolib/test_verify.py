import pathlib
import json

import autolib

import pytest


_SPECIFICATION_FILE = pathlib.Path(__file__).parent / "specification.json"
with _SPECIFICATION_FILE.open("r") as f:
    _SPECIFICATION = json.load(f)

AT = autolib.AutoTool(specification=_SPECIFICATION)


class TestVerify:
    def test_bad_path(self):
        with pytest.raises(autolib.ValidationError, match="Path '/dns/dom' is not valid."):
            AT.verify(AT.parse(["dns", "dom"]))
        with pytest.raises(autolib.ValidationError, match="Path '/dns/domain' is not valid."):
            AT.verify(AT.parse(["dns", "domain"]))
            
    def test_bad_path_with_variable(self):
        with pytest.raises(autolib.ValidationError, match="Path '/dns/{domains}' is not valid."):
            AT.verify(AT.parse(["dns", "domains=all"]))

    def test_missing_path_variable(self):
        with pytest.raises(autolib.ValidationError, match="Path variable 'domain' has not been set."):
            AT.verify(AT.parse(["dns", "domain=", "a"]))

    def test_missing_X(self):
        with pytest.raises(autolib.ValidationError, match="Method has not been set."):
            AT.verify(AT.parse(["dns", "domain=example.org", "a", "-H", "Authorization", "Bearer 0123456789", "-Q", "name", "foo", "-D", '']))

    def test_bad_X(self):
        with pytest.raises(autolib.ValidationError, match="Method 'delete' is not supported."):
            AT.verify(AT.parse(["dns", "domain=example.org", "a", "-X", "delete"]))

    def test_missing_H(self):
        with pytest.raises(autolib.ValidationError, match="Header 'Authorization' has not been set."):
            AT.verify(AT.parse(["dns", "domain=example.org", "a", "-X", "post"]))

    def test_missing_Q(self):
        with pytest.raises(autolib.ValidationError, match="Query 'name' has not been set."):
            AT.verify(AT.parse(["dns", "domain=example.org", "a", "-X", "post", "-H", "Authorization", "Bearer 0123456789"]))

    def test_missing_D(self):
        with pytest.raises(autolib.ValidationError, match="Data has not been set."):
            AT.verify(AT.parse(["dns", "domain=example.org", "a", "-X", "post", "-H", "Authorization", "Bearer 0123456789", "-Q", "name", "foo"]))

    def test_invalid_D(self):
        raise pytest.skip("Data validation is not implemented.")

    def test_ok(self):
        AT.verify(AT.parse(["dns", "domain=example.org", "a", "-X", "post", "-H", "Authorization", "Bearer 0123456789", "-Q", "name", "foo", "-D", '{}']))
