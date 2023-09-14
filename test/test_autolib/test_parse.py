import pathlib
import json

import autolib

_SPECIFICATION_FILE = pathlib.Path(__file__).parent / "specification.json"
with _SPECIFICATION_FILE.open("r") as f:
    _SPECIFICATION = json.load(f)

AT = autolib.AutoTool(specification=_SPECIFICATION)


class TestParsePath:
    def test_dns_domains(self):
        expected = autolib.Query(
            path="/dns/domains",
            method="get",
            headers={"Authorization": "Bearer 0123456789"},
        )
        actual = AT.parse(["dns", "domains", "-X", "GET", "-H", "Authorization", "Bearer 0123456789"])
        assert expected == actual

    def test_dns_domain_empty(self):
        expected = autolib.Query(path="/dns/{domain}", path_variables={"domain": ""})
        actual = AT.parse(["dns", "domain="])
        assert expected == actual

    def test_dns_domain_filled(self):
        expected = autolib.Query(path="/dns/{domain}", path_variables={"domain": "example.org"})
        actual = AT.parse(["dns", "domain=example.org"])
        assert expected == actual

    def test_dns_domain_empty_a(self):
        expected = autolib.Query(path="/dns/{domain}/a", path_variables={"domain": ""})
        actual = AT.parse(["dns", "domain=", "a"])
        assert expected == actual
    
    def test_dns_domain_filled_a(self):
        expected = autolib.Query(path="/dns/{domain}/a", path_variables={"domain": "example.org"})
        actual = AT.parse(["dns", "domain=example.org", "a"])
        assert expected == actual


class TestParseArguments:
    def test_X(self):
        expected = autolib.Query(path="/dns/domains", method="get")
        actual1 = AT.parse(["dns", "domains", "-X", "get"])
        actual2 = AT.parse(["dns", "domains", "-X", "GET"])
        assert expected == actual1
        assert expected == actual2

    def test_H(self):
        expected = autolib.Query(path="/dns/domains", headers={"Authorization": "Bearer 0123456789"})
        actual = AT.parse(["dns", "domains", "-H", "Authorization", "Bearer 0123456789"])
        assert expected == actual

    def test_H_empty(self):
        expected = autolib.Query(path="/dns/domains", headers={"Authorization": ""})
        actual = AT.parse(["dns", "domains", "-H", "Authorization"])
        assert expected == actual

    def test_XH(self):
        expected = autolib.Query(path="/dns/domains", method="get", headers={"Authorization": "Bearer 0123456789"})
        actual1 = AT.parse(["dns", "domains", "-X", "GET", "-H", "Authorization", "Bearer 0123456789"])
        actual2 = AT.parse(["dns", "domains", "-H", "Authorization", "Bearer 0123456789", "-X", "GET"])
        assert expected == actual1
        assert expected == actual2

    def test_Q(self):
        expected = autolib.Query(path="/dns/{domain}/a", path_variables={"domain": ""}, queries={"name": "foo"})
        actual = AT.parse(["dns", "domain=", "a", "-Q", "name", "foo"])
        assert expected == actual

    def test_Q_empty(self):
        expected = autolib.Query(path="/dns/{domain}/a", path_variables={"domain": ""}, queries={"name": ""})
        actual = AT.parse(["dns", "domain=", "a", "-Q", "name"])
        assert expected == actual

    def test_HQ(self):
        expected = autolib.Query(
            path="/dns/{domain}/a",
            path_variables={"domain": ""},
            headers={"Authorization": "Bearer 0123456789"},
            queries={"name": "foo"},
        )
        actual = AT.parse(["dns", "domain=", "a", "-H", "Authorization", "Bearer 0123456789", "-Q", "name", "foo"])
        assert expected == actual

    def test_XQ(self):
        expected = autolib.Query(
            path="/dns/{domain}/a",
            path_variables={"domain": ""},
            method="post",
            queries={"name": "foo"},
        )
        actual = AT.parse(["dns", "domain=", "a", "-X", "POST", "-Q", "name", "foo"])
        assert expected == actual

    def test_XHQ(self):
        expected = autolib.Query(
            path="/dns/{domain}/a",
            path_variables={"domain": ""},
            method="post",
            headers={"Authorization": "Bearer 0123456789"},
            queries={"name": "foo"},
        )
        actual = AT.parse(["dns", "domain=", "a", "-X", "post", "-H", "Authorization", "Bearer 0123456789", "-Q", "name", "foo"])
        assert expected == actual

    def test_D(self):
        expected = autolib.Query(
            path="/dns/{domain}/a",
            path_variables={"domain": ""},
            data='{"foo": "bar"}',
        )
        actual = AT.parse(["dns", "domain=", "a", "-D", '{"foo": "bar"}'])
        assert expected == actual
