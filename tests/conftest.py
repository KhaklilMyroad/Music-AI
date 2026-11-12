"""Shared test setup: nothing a test does may land in the home directory of whoever runs the tests. The journal,
the read-only flag and the remembered User Library all live under the home folder, so each test gets its own."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_environment(tmp_path_factory, monkeypatch):
    home = tmp_path_factory.mktemp("home")
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.delenv("T2A_JOURNAL_DIR", raising=False)
    monkeypatch.delenv("T2A_READ_ONLY", raising=False)
    monkeypatch.delenv("T2A_JOURNAL", raising=False)
    monkeypatch.delenv("T2A_DEMUCS_PYTHON", raising=False)
    monkeypatch.delenv("T2A_PORT", raising=False)
