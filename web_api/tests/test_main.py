import pytest
import httpx

@pytest.mark.asyncio
async def test_health_check(async_client: httpx.AsyncClient):
    """
    Test the /health endpoint to ensure the API is running correctly.
    """
    response = await async_client.get("/health")
    
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "app_db" in data
    assert "db_provider" in data
