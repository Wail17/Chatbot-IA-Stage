"""Tests for the chat endpoint."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import ChatResponse


client = TestClient(app)


def test_health_check() -> None:
    """Test that the health endpoint returns 200 with expected structure."""
    response = client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "healthy"
    assert "features" in data
    assert "environment" in data


def test_chat_missing_question() -> None:
    """Test that empty question is rejected."""
    response = client.post("/api/chat", json={"question": ""})
    assert response.status_code == 422


def test_chat_question_too_long() -> None:
    """Test that overly long questions are rejected."""
    long_question = "a" * 2001
    response = client.post("/api/chat", json={"question": long_question})
    assert response.status_code == 422


@patch("app.api.chat.retrieve_answer")
def test_chat_success(mock_retrieve: AsyncMock) -> None:
    """Test successful chat response."""
    mock_retrieve.return_value = ChatResponse(
        answer="Test answer about swimming pools.",
        confidence=0.92,
        sources=[],
        used_model="claude-haiku-4-20250514",
        language="nl",
        conversation_id=1,
        session_id="test-session",
    )

    response = client.post(
        "/api/chat",
        json={"question": "Wat kost een zwembad?", "language": "nl"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "Test answer about swimming pools."
    assert data["confidence"] == 0.92
    assert data["language"] == "nl"


def test_feedback_missing_fields() -> None:
    """Test that feedback with missing fields is rejected."""
    response = client.post("/api/feedback", json={})
    assert response.status_code == 422


@patch("app.api.chat.process_feedback")
def test_feedback_success(mock_process: AsyncMock) -> None:
    """Test successful feedback submission."""
    mock_process.return_value = {"status": "recorded", "draft_id": None}

    response = client.post(
        "/api/feedback",
        json={
            "conversation_id": 1,
            "thumbs_up": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


@patch("app.api.chat.process_feedback")
def test_feedback_with_correction(mock_process: AsyncMock) -> None:
    """Test feedback with user correction creates a draft."""
    mock_process.return_value = {"status": "recorded", "draft_id": 42}

    response = client.post(
        "/api/feedback",
        json={
            "conversation_id": 1,
            "thumbs_up": False,
            "correction": "The correct answer is...",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["draft_id"] == 42
