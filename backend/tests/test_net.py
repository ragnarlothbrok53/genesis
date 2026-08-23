from genesis.core.net import host_port


def test_bare_host_uses_default_port():
    assert host_port("temporal", 7233) == ("temporal", 7233)


def test_explicit_port_wins():
    assert host_port("temporal:7999", 7233) == ("temporal", 7999)


def test_url_form_is_parsed():
    assert host_port("http://openobserve:5080/o11y/api/default", 5080) == ("openobserve", 5080)


def test_url_without_port_falls_back():
    assert host_port("https://otel.example.com/v1", 4318) == ("otel.example.com", 4318)


def test_empty_address_defaults_to_loopback():
    assert host_port("", 5432) == ("127.0.0.1", 5432)
