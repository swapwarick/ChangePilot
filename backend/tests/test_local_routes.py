"""Tests for local directory browsing, search, and repo info endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_get_local_repo_info_valid(tmp_path: Path):
    res = client.get(f"/local/info?path={tmp_path}")
    assert res.status_code == 200
    data = res.json()
    assert data["valid"] is True
    assert data["name"] == tmp_path.name
    assert data["is_git"] is False


def test_browse_directory_root():
    res = client.get("/local/browse")
    assert res.status_code == 200
    data = res.json()
    assert "entries" in data
    assert len(data["entries"]) > 0


def test_browse_directory_specific(tmp_path: Path):
    sub = tmp_path / "subfolder"
    sub.mkdir()
    res = client.get(f"/local/browse?path={tmp_path}")
    assert res.status_code == 200
    data = res.json()
    assert data["current_path"] == str(tmp_path)
    entry_names = [e["name"] for e in data["entries"]]
    assert "subfolder" in entry_names


def test_search_directories(tmp_path: Path):
    target = tmp_path / "my_unique_search_target_dir"
    target.mkdir()
    res = client.get(f"/local/search?query=unique_search_target&root={tmp_path}")
    assert res.status_code == 200
    data = res.json()
    assert len(data) >= 1
    assert data[0]["name"] == "my_unique_search_target_dir"


def test_get_ai_providers():
    res = client.get("/ai-providers")
    assert res.status_code == 200
    assert isinstance(res.json(), list)

