import pytest
from fastapi import status
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock, AsyncMock
import pandas as pd
import os
from pathlib import Path

from app.main import app
from app.Models.Schema import ConsultaParams


@pytest.fixture
def client():
    """Fixture que fornece um TestClient do FastAPI."""
    return TestClient(app)


@pytest.fixture
def mock_consulta_service(mocker):
    """Mock do ConsultaService."""
    mock_service = mocker.patch('app.Routes.routes.consulta_service')
    mock_service.consulta_repo = Mock()
    mock_service.cancelar_consulta = Mock()
    return mock_service


@pytest.fixture
def mock_system_status(mocker):
    """Mock da função get_system_status."""
    return mocker.patch('app.Routes.routes.get_system_status')


@pytest.fixture
def mock_performance_tracker(mocker):
    """Mock do performance_tracker."""
    return mocker.patch('app.Routes.routes.performance_tracker')


class TestConsultarEndpoint:
    """Testes para o endpoint POST /consultar."""
    
    def test_consultar_ano_unico_sucesso(self, client, mock_consulta_service):
        """Testa consulta síncrona de um único ano com sucesso."""
        # Arrange
        payload = {
            "data_inicio": "01/2023",
            "data_fim": "12/2023"
        }
        
        resultado_mock = {
            "dados": [{"teste": "dados"}],
            "total_registros": 1,
            "ano": 2023
        }
        
        mock_consulta_service.processar_consulta = AsyncMock(return_value=resultado_mock)
        
        # Act
        response = client.post("/consultar", json=payload)
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert "dados" in response.json()
        assert response.json()["total_registros"] == 1
    
    def test_consultar_multiplos_anos_retorna_202(self, client, mock_consulta_service):
        """Testa consulta assíncrona de múltiplos anos retorna 202."""
        # Arrange
        payload = {
            "data_inicio": "01/2020",
            "data_fim": "12/2023"
        }
        
        resultado_mock = {
            "id_consulta": "test_123",
            "status": "processando",
            "mensagem": "Consulta iniciada"
        }
        
        mock_consulta_service.processar_consulta = AsyncMock(return_value=resultado_mock)
        
        # Act
        response = client.post("/consultar", json=payload)
        
        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED
        assert "id_consulta" in response.json()
        assert response.json()["status"] == "processando"
    
    def test_consultar_com_dados_invalidos(self, client, mock_consulta_service):
        """Testa validação de dados inválidos retorna 400."""
        # Arrange
        payload = {
            "data_inicio": "13/2023",  # Mês inválido
            "data_fim": "12/2023"
        }
        
        mock_consulta_service.processar_consulta = AsyncMock(
            side_effect=ValueError("Mês inválido")
        )
        
        # Act
        response = client.post("/consultar", json=payload)
        
        # Assert
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "error" in response.json()
    
    def test_consultar_erro_interno(self, client, mock_consulta_service):
        """Testa erro interno retorna 500."""
        # Arrange
        payload = {
            "data_inicio": "01/2023",
            "data_fim": "12/2023"
        }
        
        mock_consulta_service.processar_consulta = AsyncMock(
            side_effect=Exception("Erro inesperado")
        )
        
        # Act
        response = client.post("/consultar", json=payload)
        
        # Assert
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "error" in response.json()


class TestObterStatusConsulta:
    """Testes para o endpoint GET /status-consulta/{id_consulta}."""
    
    def test_obter_status_consulta_processando(self, client, mock_consulta_service):
        """Testa obtenção de status de consulta em processamento."""
        # Arrange
        id_consulta = "test_123"
        
        consulta_mock = {
            "status": "processando",
            "anos_concluidos": [2020],
            "anos_pendentes": [2021, 2022, 2023],
            "total_registros_ate_agora": 100
        }
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = consulta_mock
        
        # Act
        response = client.get(f"/status-consulta/{id_consulta}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "processando"
        assert "progresso" in data
        assert data["progresso"]["total_anos"] == 4
        assert data["progresso"]["anos_processados"] == 1
    
    def test_obter_status_consulta_concluida(self, client, mock_consulta_service):
        """Testa obtenção de status de consulta concluída."""
        # Arrange
        id_consulta = "test_456"
        
        consulta_mock = {
            "status": "concluido",
            "anos_concluidos": [2020, 2021, 2022],
            "anos_pendentes": [],
            "dados_por_ano": {
                "2020": {"dados": [], "total_registros": 50},
                "2021": {"dados": [], "total_registros": 60},
                "2022": {"dados": [], "total_registros": 70}
            }
        }
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = consulta_mock
        
        # Act
        response = client.get(f"/status-consulta/{id_consulta}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "concluido"
        assert "endpoints_dados_por_ano" in data
    
    def test_obter_status_consulta_nao_encontrada(self, client, mock_consulta_service):
        """Testa busca de consulta inexistente retorna 404."""
        # Arrange
        id_consulta = "inexistente"
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = {
            "error": "Consulta não encontrada"
        }
        
        # Act
        response = client.get(f"/status-consulta/{id_consulta}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestObterConsultaCompleta:
    """Testes para o endpoint GET /consulta/{id_consulta}."""
    
    def test_obter_consulta_completa_sucesso(self, client, mock_consulta_service):
        """Testa obtenção completa de consulta bem-sucedida."""
        # Arrange
        id_consulta = "test_789"
        
        consulta_mock = {
            "status": "concluido",
            "dados_por_ano": {
                "2023": {
                    "dados": [{"registro": 1}],
                    "total_registros": 1
                }
            },
            "total_registros": 1
        }
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = consulta_mock
        
        # Act
        response = client.get(f"/consulta/{id_consulta}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "concluido"
    
    def test_obter_consulta_completa_nao_encontrada(self, client, mock_consulta_service):
        """Testa consulta não encontrada retorna 404."""
        # Arrange
        id_consulta = "inexistente"
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = {
            "error": "Consulta não encontrada"
        }
        
        # Act
        response = client.get(f"/consulta/{id_consulta}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestObterDadosAno:
    """Testes para o endpoint GET /consulta/{id_consulta}/ano/{ano}."""
    
    def test_obter_dados_ano_sucesso(self, client, mock_consulta_service):
        """Testa obtenção de dados de um ano específico."""
        # Arrange
        id_consulta = "test_abc"
        ano = 2023
        
        consulta_mock = {
            "status": "concluido",
            "anos_concluidos": [2023],
            "anos_pendentes": [],
            "dados_por_ano": {
                "2023": {
                    "dados": [{"registro": 1}, {"registro": 2}],
                    "total_registros": 2,
                    "mes_inicio": 1,
                    "mes_fim": 12,
                    "processado_em": "2024-01-01 10:00:00"
                }
            },
            "resumo_por_ano": {
                "2023": {
                    "total_registros": 2,
                    "valores_totais": {"ORCAMENTO": 1000000}
                }
            }
        }
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = consulta_mock
        
        # Act
        response = client.get(f"/consulta/{id_consulta}/ano/{ano}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["ano"] == ano
        assert data["total_registros"] == 2
        assert len(data["dados"]) == 2
        assert "resumo_estatistico" in data
    
    def test_obter_dados_ano_pendente(self, client, mock_consulta_service):
        """Testa ano ainda em processamento retorna 202."""
        # Arrange
        id_consulta = "test_def"
        ano = 2023
        
        consulta_mock = {
            "status": "processando",
            "anos_concluidos": [],
            "anos_pendentes": [2023]
        }
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = consulta_mock
        
        # Act
        response = client.get(f"/consulta/{id_consulta}/ano/{ano}")
        
        # Assert
        assert response.status_code == status.HTTP_202_ACCEPTED
    
    def test_obter_dados_ano_nao_encontrado(self, client, mock_consulta_service):
        """Testa ano não processado retorna 404."""
        # Arrange
        id_consulta = "test_ghi"
        ano = 2025
        
        consulta_mock = {
            "status": "concluido",
            "anos_concluidos": [2023],
            "anos_pendentes": []
        }
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = consulta_mock
        
        # Act
        response = client.get(f"/consulta/{id_consulta}/ano/{ano}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestObterAnosDisponiveis:
    """Testes para o endpoint GET /consulta/{id_consulta}/anos-disponiveis."""
    
    def test_obter_anos_disponiveis_sucesso(self, client, mock_consulta_service):
        """Testa listagem de anos disponíveis."""
        # Arrange
        id_consulta = "test_jkl"
        
        consulta_mock = {
            "status": "concluido",
            "anos_concluidos": [2020, 2021, 2022],
            "anos_pendentes": [],
            "dados_por_ano": {
                "2020": {"dados": [], "total_registros": 50, "mes_inicio": 1, "mes_fim": 12},
                "2021": {"dados": [], "total_registros": 60, "mes_inicio": 1, "mes_fim": 12},
                "2022": {"dados": [], "total_registros": 70, "mes_inicio": 1, "mes_fim": 12}
            },
            "resumo_por_ano": {
                "2020": {"valores_totais": {}, "unidades_orcamentarias": ["UEL"], "funcoes": []},
                "2021": {"valores_totais": {}, "unidades_orcamentarias": ["UEM"], "funcoes": []},
                "2022": {"valores_totais": {}, "unidades_orcamentarias": ["UEPG"], "funcoes": []}
            },
            "periodo_consulta": {"mes_inicio": 1, "mes_fim": 12}
        }
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = consulta_mock
        
        # Act
        response = client.get(f"/consulta/{id_consulta}/anos-disponiveis")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["organizacao"] == "por_ano"
        assert len(data["anos_concluidos"]) == 3
        assert "detalhes_por_ano" in data
        
        # CORRIGIDO: Verificar com string em vez de inteiro
        assert "2020" in data["detalhes_por_ano"]
        assert "2021" in data["detalhes_por_ano"]
        assert "2022" in data["detalhes_por_ano"]
        
        # Verificar estrutura dos detalhes
        detalhes_2020 = data["detalhes_por_ano"]["2020"]
        assert detalhes_2020["status"] == "concluido"
        assert detalhes_2020["total_registros"] == 50
        assert detalhes_2020["mes_inicio"] == 1
        assert detalhes_2020["mes_fim"] == 12


class TestSystemStatus:
    """Testes para o endpoint GET /system-status."""
    
    def test_get_system_status(self, client, mock_system_status):
        """Testa obtenção de status do sistema."""
        # Arrange
        status_mock = {
            "status": "online",
            "versao": "1.0.0",
            "recursos_disponiveis": {
                "cpu": "50%",
                "memoria": "2GB/8GB"
            }
        }
        
        mock_system_status.return_value = status_mock
        
        # Act
        response = client.get("/system-status")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        assert response.json()["status"] == "online"


class TestPerformanceMetrics:
    """Testes para endpoints de métricas de performance."""
    
    def test_obter_metricas_performance_arquivo_nao_existe(self, client, mock_performance_tracker):
        """Testa quando arquivo de métricas não existe."""
        # Arrange
        mock_performance_tracker.csv_path = "caminho/inexistente.csv"
        
        # Act
        response = client.get("/performance-metrics")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "error" in response.json()
    
    def test_obter_metricas_performance_arquivo_vazio(self, client, mock_performance_tracker, tmp_path, mocker):
        """Testa quando arquivo CSV está vazio."""
        # Arrange
        csv_path = tmp_path / "metricas.csv"
        csv_path.write_text("timestamp,operation,sucesso,tempo_total_segundos,numero_registros\n")
        
        mock_performance_tracker.csv_path = str(csv_path)
        mocker.patch('os.path.exists', return_value=True)
        mocker.patch('pandas.read_csv', return_value=pd.DataFrame())
        
        # Act
        response = client.get("/performance-metrics")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["estatisticas"]["total_consultas"] == 0
    
    def test_obter_metricas_performance_com_dados(self, client, mock_performance_tracker, tmp_path, mocker):
        """Testa obtenção de métricas com dados."""
        # Arrange
        df_mock = pd.DataFrame({
            'timestamp': ['2024-01-01 10:00:00', '2024-01-01 11:00:00'],
            'operation': ['consulta_sincrona', 'consulta_sincrona'],
            'sucesso': [True, True],
            'tempo_total_segundos': [10.5, 15.2],
            'numero_registros': [100, 150],
            'ano_inicio': [2023, 2023],
            'ano_fim': [2023, 2023]
        })
        
        csv_path = tmp_path / "metricas.csv"
        mock_performance_tracker.csv_path = str(csv_path)
        
        mocker.patch('os.path.exists', return_value=True)
        mocker.patch('pandas.read_csv', return_value=df_mock)
        
        # Act
        response = client.get("/performance-metrics")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["estatisticas"]["total_consultas"] == 2
        assert data["estatisticas"]["consultas_bem_sucedidas"] == 2
        assert "processamento_por_ano" in data["estatisticas"]


class TestPerformanceSummary:
    """Testes para o endpoint GET /performance-summary."""
    
    def test_obter_resumo_performance_arquivo_nao_existe(self, client, mock_performance_tracker):
        """Testa quando arquivo não existe."""
        # Arrange
        mock_performance_tracker.csv_path = "inexistente.csv"
        
        # Act
        response = client.get("/performance-summary")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_obter_resumo_performance_com_dados(self, client, mock_performance_tracker, tmp_path, mocker):
        """Testa obtenção de resumo com dados."""
        # Arrange
        df_mock = pd.DataFrame({
            'timestamp': ['2024-01-01 10:00:00', '2024-01-01 11:00:00', '2024-01-01 12:00:00'],
            'operation': ['consulta_sincrona', 'consulta_assincrona_final', 'consulta_sincrona'],
            'sucesso': [True, True, False],
            'tempo_total_segundos': [10.5, 25.3, 5.2],
            'numero_registros': [100, 300, 0],
            'ano_inicio': [2023, 2020, 2023],
            'ano_fim': [2023, 2023, 2023]
        })
        
        csv_path = tmp_path / "metricas.csv"
        mock_performance_tracker.csv_path = str(csv_path)
        
        mocker.patch('os.path.exists', return_value=True)
        mocker.patch('pandas.read_csv', return_value=df_mock)
        
        # Act
        response = client.get("/performance-summary")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert "periodo_analise" in data
        assert "consultas" in data
        assert "performance" in data
        assert data["organizacao"] == "por_ano"


class TestCancelarConsulta:
    """Testes para o endpoint POST /cancelar-consulta/{id_consulta}."""
    
    def test_cancelar_consulta_em_processamento(self, client, mock_consulta_service):
        """Testa cancelamento de consulta em andamento."""
        # Arrange
        id_consulta = "test_cancel_1"
        
        consulta_mock = {
            "status": "processando",
            "id_consulta": id_consulta
        }
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = consulta_mock
        mock_consulta_service.cancelar_consulta.return_value = {"status": "cancelado"}
        
        # Act
        response = client.post(f"/cancelar-consulta/{id_consulta}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "cancelamento_solicitado"
    
    def test_cancelar_consulta_ja_concluida(self, client, mock_consulta_service):
        """Testa tentativa de cancelar consulta já concluída."""
        # Arrange
        id_consulta = "test_cancel_2"
        
        consulta_mock = {
            "status": "concluido",
            "id_consulta": id_consulta
        }
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = consulta_mock
        
        # Act
        response = client.post(f"/cancelar-consulta/{id_consulta}")
        
        # Assert
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "erro"
        assert "não pode ser cancelada" in data["mensagem"]
    
    def test_cancelar_consulta_nao_encontrada(self, client, mock_consulta_service):
        """Testa cancelamento de consulta inexistente."""
        # Arrange
        id_consulta = "inexistente"
        
        mock_consulta_service.consulta_repo.obter_consulta.return_value = {
            "error": "Consulta não encontrada"
        }
        
        # Act
        response = client.post(f"/cancelar-consulta/{id_consulta}")
        
        # Assert
        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestConvertNumpyTypes:
    """Testes para a função auxiliar convert_numpy_types."""
    
    def test_convert_none(self):
        """Testa conversão de None."""
        from app.Routes.routes import convert_numpy_types
        
        assert convert_numpy_types(None) is None
    
    def test_convert_nan(self):
        """Testa conversão de NaN."""
        from app.Routes.routes import convert_numpy_types
        import numpy as np
        
        assert convert_numpy_types(np.nan) is None
    
    def test_convert_numpy_int(self):
        """Testa conversão de numpy int."""
        from app.Routes.routes import convert_numpy_types
        import numpy as np
        
        result = convert_numpy_types(np.int64(42))
        assert result == 42
        assert isinstance(result, int)
    
    def test_convert_numpy_float(self):
        """Testa conversão de numpy float."""
        from app.Routes.routes import convert_numpy_types
        import numpy as np
        
        result = convert_numpy_types(np.float64(3.14))
        assert result == 3.14
        assert isinstance(result, float)
    
    def test_convert_pandas_timestamp(self):
        """Testa conversão de pandas Timestamp."""
        from app.Routes.routes import convert_numpy_types
        import pandas as pd
        
        ts = pd.Timestamp('2024-01-01')
        result = convert_numpy_types(ts)
        assert isinstance(result, str)
    
    def test_convert_bool(self):
        """Testa conversão de bool."""
        from app.Routes.routes import convert_numpy_types
        
        assert convert_numpy_types(True) is True
        assert convert_numpy_types(False) is False


class TestIntegracaoRotas:
    """Testes de integração entre rotas."""
    
    def test_fluxo_completo_consulta_ano_unico(self, client, mock_consulta_service):
        """Testa fluxo completo: consulta -> obter status -> obter dados."""
        # Arrange
        payload = {"data_inicio": "01/2023", "data_fim": "12/2023"}
        
        # Mock da consulta inicial (síncrona)
        resultado_consulta = {
            "dados": [{"registro": 1}],
            "total_registros": 1,
            "ano": 2023
        }
        mock_consulta_service.processar_consulta = AsyncMock(return_value=resultado_consulta)
        
        # Act 1: Fazer consulta
        response_consulta = client.post("/consultar", json=payload)
        
        # Assert 1
        assert response_consulta.status_code == status.HTTP_200_OK
        assert "dados" in response_consulta.json()