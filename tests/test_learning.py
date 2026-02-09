"""Tests for the learning system."""

from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


@patch("app.api.learning.run_learning_cycle")
def test_trigger_learning(mock_cycle: AsyncMock) -> None:
    """Test manual learning cycle trigger."""
    mock_cycle.return_value = {"drafts_created": 3, "signals_processed": 15}

    response = client.post("/api/learning/trigger")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "3" in data["message"]


@patch("app.api.learning.get_learning_stats")
def test_learning_stats(mock_stats: AsyncMock) -> None:
    """Test learning statistics endpoint."""
    mock_stats.return_value = {
        "unprocessed_signals": 5,
        "pending_drafts": 2,
        "approved_drafts": 10,
        "total_knowledge_entries": 150,
        "nightly_learning_enabled": True,
        "min_cluster_size": 5,
        "auto_draft_threshold": 0.80,
    }

    response = client.get("/api/learning/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["unprocessed_signals"] == 5
    assert data["total_knowledge_entries"] == 150


@patch("app.api.admin.get_pending_drafts")
def test_list_drafts(mock_drafts: AsyncMock) -> None:
    """Test admin draft listing endpoint."""
    mock_drafts.return_value = []

    response = client.get("/api/admin/drafts?status=pending")

    assert response.status_code == 200
    assert response.json() == []


@patch("app.api.admin.get_performance_stats")
def test_performance_stats(mock_stats: AsyncMock) -> None:
    """Test admin performance endpoint."""
    mock_stats.return_value = []

    response = client.get("/api/admin/performance?weeks=4")

    assert response.status_code == 200
    assert response.json() == []
