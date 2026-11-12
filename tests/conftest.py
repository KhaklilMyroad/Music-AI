"""Shared test setup: the action journal goes to a temporary folder, never to the home directory of whoever runs the tests."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_environment(tmp_path_factory, monkeypatch):
    monkeypatch.setenv("T2A_JOURNAL_DIR", str(tmp_path_factory.mktemp("journal")))
    monkeypatch.delenv("T2A_READ_ONLY", raising=False)
    monkeypatch.delenv("T2A_JOURNAL", raising=False)
    monkeypatch.delenv("T2A_DEMUCS_PYTHON", raising=False)
