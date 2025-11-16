import pytest
from unittest.mock import Mock
import pandas as pd

@pytest.fixture
def mock_background_tasks():
    """Mock para BackgroundTasks do FastAPI."""
    mock = Mock()
    mock.add_task = Mock()
    return mock

@pytest.fixture
def consulta_params_factory():
    """Factory para criar ConsultaParams."""
    def _create(data_inicio="01/2023", data_fim="12/2023"):
        from app.Models.Schema import ConsultaParams
        return ConsultaParams(
            data_inicio=data_inicio,
            data_fim=data_fim
        )
    return _create

@pytest.fixture
def mock_estrategia():
    """Mock para EstrategiaProcessamento."""
    estrategia = Mock()
    estrategia.usar_dados_locais = True
    estrategia.fonte = "local"
    estrategia.periodo = Mock()
    estrategia.periodo.mes_inicio = 1
    estrategia.periodo.mes_fim = 12
    return estrategia

@pytest.fixture
def df_despesas_mock():
    """DataFrame mock com estrutura de despesas."""
    return pd.DataFrame({
        'UNIDADE ORÇAMENTÁRIA': ['UEL', 'UEM', 'TECPAR'],
        'FUNÇÃO': ['EDUCAÇÃO', 'EDUCAÇÃO', 'C&T'],
        'GRUPO DE NATUREZA DE DESPESA': ['CORRENTES'] * 3,
        'ORIGEM DOS RECURSOS': ['ORDINÁRIOS'] * 3,
        'VALOR': [1000, 2000, 500]
    })

@pytest.fixture
def consulta_params_valida():
    """Parâmetros de consulta válidos."""
    return {
        "data_inicio": "01/2023",
        "data_fim": "12/2023"
    }

@pytest.fixture
def consulta_params_multiplos_anos():
    """Parâmetros para consulta de múltiplos anos."""
    return {
        "data_inicio": "01/2020",
        "data_fim": "12/2023"
    }