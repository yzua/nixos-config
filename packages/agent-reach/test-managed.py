"""Offline checks for the Nix-managed browser and explicit session imports."""

from pathlib import Path

from agent_reach.runtime import browser, session_reuse


def test_managed_browser_does_not_install_cloak(monkeypatch):
    from agent_reach.backends import cloak

    def unexpected():
        raise AssertionError("managed Chrome must not download CloakBrowser")

    saved = {}
    monkeypatch.setattr(cloak, "setup", unexpected)
    monkeypatch.setattr(browser, "update_state", lambda **values: saved.update(values))
    executable = browser.ensure_chrome(retry_cloak=True)
    assert executable.startswith("/nix/store/")
    assert Path(executable).is_file()
    assert saved["backend"] == "chrome"
    assert saved["executable"] == executable


def test_managed_extension_is_already_available():
    assert str(browser.extension_dir()).startswith("/nix/store/")
    assert browser.extension_version() == "1.0.23"
    assert browser.refresh_extension() == {"version": "1.0.23", "updated": False}


def test_session_import_is_explicit(monkeypatch):
    from contextlib import nullcontext

    def unexpected(*args):
        raise AssertionError("ordinary queries must not copy another browser's cookies")

    monkeypatch.setattr(browser, "ensure_running", lambda: None)
    monkeypatch.setattr(session_reuse, "wait_lock", lambda _: nullcontext())
    monkeypatch.setattr(session_reuse.state, "load", lambda: {})
    monkeypatch.setattr(session_reuse, "_source_cookies", unexpected)
    for channel in ("twitter", "reddit"):
        assert session_reuse.prepare(channel) == {
            "source": "explicit_import_only",
            "copied_cookies": 0,
        }
