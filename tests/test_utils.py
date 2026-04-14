def test_get_geo_data_caches_success_but_not_failures(monkeypatch):
    from server import utils

    utils._geo_cache.clear()
    calls = []

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def json(self):
            return self._payload

    def fake_get(url, params, timeout):
        calls.append(url)
        if len(calls) == 1:
            return _Resp({"status": "fail"})
        return _Resp({"status": "success", "countryCode": "IT", "org": "ISP"})

    monkeypatch.setattr(utils.http_session, "get", fake_get)

    first = utils.get_geo_data("8.8.8.8")
    second = utils.get_geo_data("8.8.8.8")
    third = utils.get_geo_data("8.8.8.8")

    assert first == {}
    assert second["countryCode"] == "IT"
    assert third["countryCode"] == "IT"
    assert len(calls) == 2
