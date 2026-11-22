from app.services import hosting_enrich as he

IP_DOC = {"name": "EXAMPLE-NET", "handle": "NET-1", "country": "NL", "startAddress": "203.0.113.0", "endAddress": "203.0.113.255",
          "cidr0_cidrs": [{"v4prefix": "203.0.113.0", "length": 24}], "entities": [{"vcardArray": ["vcard", [["fn", {}, "text", "Example Hosting BV"]]]}]}
DOM_DOC = {"events": [{"eventAction": "registration", "eventDate": "2020-01-02T00:00:00Z"}, {"eventAction": "last changed", "eventDate": "2026-05-01T00:00:00Z"}],
           "entities": [{"roles": ["registrar"], "vcardArray": ["vcard", [["fn", {}, "text", "Some Registrar"]]]}],
           "status": ["client transfer prohibited"], "nameservers": [{"ldhName": "ns1.example.net"}]}


def _fetch(url, timeout):
    return IP_DOC if "/ip/" in url else DOM_DOC


FP = {"domain": "example.org", "server_ips": ["93.184.216.34", "10.0.0.5"], "country": "Not resolved", "label": "Hosting server, not the creator"}


def test_disabled_by_default_makes_no_lookups():
    called = []
    out = he.enrich(FP, enabled=False, fetch=lambda u, t: called.append(u))
    assert out["enrichment"]["status"] == "disabled" and not called and out["label"] == "Hosting server, not the creator"


def test_enrichment_parses_network_and_domain_and_skips_private_ips():
    urls = []
    def fetch(u, t):
        urls.append(u); return _fetch(u, t)
    out = he.enrich(FP, enabled=True, fetch=fetch)
    e = out["enrichment"]
    assert e["status"] == "ok" and e["networks"][0]["network_name"] == "EXAMPLE-NET" and e["networks"][0]["cidrs"] == ["203.0.113.0/24"]
    assert e["domain"]["registrar"] == "Some Registrar" and e["domain"]["registered"].startswith("2020")
    assert not any("10.0.0.5" in u for u in urls)
    assert "not a precise location" in out["country"]


def test_failures_are_recorded_not_raised():
    def boom(u, t):
        raise TimeoutError("x")
    e = he.enrich(FP, enabled=True, fetch=boom)["enrichment"]
    assert e["status"] == "unavailable" and e["notes"]


def test_domain_that_is_an_ip_is_not_looked_up_as_a_domain():
    urls = []
    he.enrich({"domain": "93.184.216.35", "server_ips": ["93.184.216.35"]}, enabled=True, fetch=lambda u, t: (urls.append(u), IP_DOC)[1])
    assert all("/domain/" not in u for u in urls)
