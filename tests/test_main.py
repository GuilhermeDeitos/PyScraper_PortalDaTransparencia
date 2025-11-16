import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)
  
def test_app_creation(client):
    """Testa se a aplicação FastAPI foi criada corretamente."""
    # Arrange & Act
    response = client.get("/docs")
    
    # Assert
    assert response.status_code == 200

def test_app_metadata(client):
    """Testa os metadados da aplicação."""
    # Arrange & Act
    response = client.get("/openapi.json")
    data = response.json()
    
    # Assert
    assert response.status_code == 200
    assert data["info"]["title"] == "API Crawler Transparência PR"
    assert data["info"]["version"] == "1.0.0"

@pytest.mark.integration
def test_health_check(client):
    """Testa o endpoint de health check (se existir)."""
    # Arrange & Act
    response = client.get("/")
    
    # Assert
    # Ajuste conforme sua rota raiz
    assert response.status_code in [200, 404]