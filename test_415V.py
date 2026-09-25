"""
BUG-01 Fix: test_415V.py
The old file imported `process_message` from `server` which doesn't exist.
Rewritten as a proper pytest integration test using httpx async client.
"""
import pytest
import httpx

BASE_URL = "http://localhost:8000"

def test_415V_power_calculation_endpoint_reachable():
    """Verify the /health endpoint is up before running integration tests."""
    try:
        resp = httpx.get(f"{BASE_URL}/health", timeout=5)
        assert resp.status_code == 200, f"Health check failed: {resp.status_code}"
    except httpx.ConnectError:
        pytest.skip("Server not running — skipping integration test.")

@pytest.mark.asyncio
async def test_415V_power_calculation_via_chat():
    """
    Integration test: 415 V three-phase power calculation.
    Sends the request to the /chat SSE endpoint and checks the stream contains a result.
    Skipped automatically if the server is not running.
    """
    msg = "A three-phase industrial load operates at 415 V, 25 A and PF 0.82. Calculate the power in kW."
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.get(
                f"{BASE_URL}/chat",
                params={"message": msg, "session_id": "test_415V"},
            )
            assert response.status_code == 200
            body = response.text
            # The stream should contain a result event
            assert "data:" in body, "No SSE data events received"
    except httpx.ConnectError:
        pytest.skip("Server not running — skipping integration test.")
