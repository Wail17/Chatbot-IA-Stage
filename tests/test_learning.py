"""Tests for the learning system and admin endpoints."""

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
        "total_signals": 20,
        "pending_drafts": 2,
        "approved_drafts": 10,
        "rejected_drafts": 3,
        "total_knowledge_entries": 150,
        "learned_entries": 12,
        "nightly_learning_enabled": True,
        "min_cluster_size": 5,
        "auto_draft_threshold": 0.80,
    }

    response = client.get("/api/learning/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["unprocessed_signals"] == 5
    assert data["total_knowledge_entries"] == 150
    assert data["learned_entries"] == 12


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


@patch("app.api.admin.get_draft_stats")
def test_draft_stats(mock_stats: AsyncMock) -> None:
    """Test draft statistics endpoint."""
    mock_stats.return_value = {
        "by_status": {"pending": 5, "approved": 10, "rejected": 2},
        "by_source": {"user_correction": 8, "pattern_detection": 9},
        "top_categories": [{"category": "Onderhoud", "count": 4}],
        "approved_this_week": 3,
    }

    response = client.get("/api/admin/drafts/stats")

    assert response.status_code == 200
    data = response.json()
    assert data["by_status"]["pending"] == 5
    assert data["approved_this_week"] == 3


@patch("app.api.admin.get_weekly_analytics")
def test_weekly_analytics(mock_analytics: AsyncMock) -> None:
    """Test weekly analytics endpoint."""
    mock_analytics.return_value = []

    response = client.get("/api/admin/analytics/weekly?weeks=4")

    assert response.status_code == 200
    assert response.json() == []


@patch("app.api.admin.get_knowledge_base_entries")
def test_list_knowledge_base(mock_kb: AsyncMock) -> None:
    """Test knowledge base listing endpoint."""
    mock_kb.return_value = []

    response = client.get("/api/admin/knowledge")

    assert response.status_code == 200
    assert response.json() == []
