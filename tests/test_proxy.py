import pytest
from schulplattform.proxy import caddyfile, hostname


@pytest.mark.parametrize('value', ['example.invalid\nadmin off', 'https://example.invalid',
    '127.0.0.1', 'example.invalid:443', '*.example.invalid', 'x..invalid', '-x.invalid', 'x.invalid/path'])
def test_domain_injections_rejected(value):
    with pytest.raises(ValueError):
        hostname(value)


def test_explicit_routes():
    config = caddyfile([('gswb', 'words.example.invalid', 8000)])
    assert 'reverse_proxy gswb:8000' in config
    assert '-X-Forwarded-*' in config
    with pytest.raises(ValueError):
        caddyfile([('a', 'same.example.invalid', 8000), ('b', 'same.example.invalid', 8001)])
