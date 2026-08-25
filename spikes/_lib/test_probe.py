import textwrap

from _lib.probe import UA, robots_allows

ROBOTS_DISALLOW = textwrap.dedent("""\
    User-agent: *
    Disallow: /private/
    Allow: /public/
    """)

ROBOTS_EMPTY = ""

SITE = "https://example.com"


def test_ua_declares_spike_identity():
    assert "pih-spike" in UA


def test_disallowed_path_rejected():
    assert robots_allows(ROBOTS_DISALLOW, f"{SITE}/private/x", SITE) is False


def test_allowed_path_ok():
    assert robots_allows(ROBOTS_DISALLOW, f"{SITE}/public/y", SITE) is True


def test_unlisted_path_defaults_allowed():
    assert robots_allows(ROBOTS_DISALLOW, f"{SITE}/news/z", SITE) is True


def test_empty_robots_allows_all():
    assert robots_allows(ROBOTS_EMPTY, f"{SITE}/anything", SITE) is True


def test_specific_ua_overrides_star():
    robots = "User-agent: pih-spike\nDisallow: /\nUser-agent: *\nAllow: /"
    assert robots_allows(robots, f"{SITE}/a", SITE, user_agent="pih-spike") is False
    assert robots_allows(robots, f"{SITE}/a", SITE, user_agent="other") is True
