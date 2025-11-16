import pytest
import time
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from fastapi import BackgroundTasks

from app.Services.consulta_service import ConsultaService
from app.Services.concurrency_manager import ConcurrencyConfig
from app.Models.Schema import ConsultaParams

class TestConsultaServiceInicializacao:
    
    def test_inicializacao_padrao(self):
        service = ConsultaService()
        
        assert service.consulta_repo is not None
        assert service.concurrency is not None
        assert service.optimizer is not None
        assert service.validator is not None
        assert isinstance(service.consultas_canceladas, set)
        assert len(service.consultas_canceladas) == 0
    
    def test_inicializacao_com_config_customizada(self):
        config = ConcurrencyConfig(max_concurrent_scrapers=4)
        service = ConsultaService(concurrency_config=config)
        
        assert service.concurrency.config.max_concurrent_scrapers == 4


class TestConsultaServiceProcessamento:
    
    @pytest.fixture
    def service(self, mocker):
        service = ConsultaService()
        mocker.patch.object(service.consulta_repo, 'iniciar_consulta')
        mocker.patch.object(service.consulta_repo, 'adicionar_metadados_ano')
        mocker.patch.object(service.consulta_repo, 'adicionar_resultados_ano')
        mocker.patch.object(service.consulta_repo, 'finalizar_consulta')
        return service
    
    @pytest.fixture
    def params_validos(self):
        return ConsultaParams(
            data_inicio="01/2023",
            data_fim="12/2023"
        )
    
    @pytest.mark.asyncio
    async def test_processar_consulta_sincrono_ano_unico(self, service, params_validos, mocker):
        mock_estrategias = {
            2023: Mock(
                usar_dados_locais=True,
                fonte="local",
                periodo=Mock(mes_inicio=1, mes_fim=12)
            )
        }
        
        mocker.patch.object(
            service.optimizer, 
            'definir_estrategia',
            return_value=mock_estrategias
        )
        
        mocker.patch.object(
            service.optimizer.consulta_local,
            'obter_dados_ano',
            return_value=[{"teste": "dados"}]
        )
        
        mocker.patch.object(
            service.concurrency,
            'get_available_slots',
            return_value=5
        )
        
        background_tasks = BackgroundTasks()
        resultado = await service.processar_consulta(params_validos, background_tasks)
        
        assert "dados" in resultado
        assert resultado["processamento"] == "sincrono"
        assert resultado["total_registros"] == 1
        assert 2023 in resultado["anos_processados"]
    
    @pytest.mark.asyncio
    async def test_processar_consulta_assincrono_multiplos_anos(self, service, mocker):
        # CORRIGIDO: Usando anos válidos (2022-2023 ao invés de 2023-2024)
        params = ConsultaParams(
            data_inicio="01/2022",
            data_fim="12/2023"
        )
        
        mock_estrategias = {
            2022: Mock(fonte="local", periodo=Mock(mes_inicio=1, mes_fim=12)),
            2023: Mock(fonte="scraper", periodo=Mock(mes_inicio=1, mes_fim=12))
        }
        
        mocker.patch.object(
            service.optimizer,
            'definir_estrategia',
            return_value=mock_estrategias
        )
        
        mocker.patch.object(
            service.optimizer,
            'calcular_estatisticas',
            return_value=(1, 1)
        )
        
        background_tasks = BackgroundTasks()
        resultado = await service.processar_consulta(params, background_tasks)
        
        assert resultado["status"] == "processando"
        assert "id_consulta" in resultado
        assert resultado["total_anos"] == 2
        assert resultado["anos_otimizados"] == 1
        assert resultado["anos_scraper"] == 1


class TestConsultaServiceDecisaoProcessamento:
    
    @pytest.fixture
    def service(self):
        return ConsultaService()
    
    def test_deve_processar_sincronamente_ano_unico_com_slots(self, service, mocker):
        mocker.patch.object(
            service.concurrency,
            'get_available_slots',
            return_value=5
        )
        
        estrategias = {2023: Mock()}
        resultado = service._deve_processar_sincronamente(1, estrategias)
        
        assert resultado is True
    
    def test_nao_deve_processar_sincronamente_multiplos_anos(self, service, mocker):
        mocker.patch.object(
            service.concurrency,
            'get_available_slots',
            return_value=5
        )
        
        estrategias = {2023: Mock(), 2022: Mock()}
        resultado = service._deve_processar_sincronamente(2, estrategias)
        
        assert resultado is False
    
    def test_nao_deve_processar_sincronamente_sem_slots(self, service, mocker):
        mocker.patch.object(
            service.concurrency,
            'get_available_slots',
            return_value=0
        )
        
        estrategias = {2023: Mock()}
        resultado = service._deve_processar_sincronamente(1, estrategias)
        
        assert resultado is False


class TestConsultaServiceProcessamentoAno:
    
    @pytest.fixture
    def service(self, mocker):
        service = ConsultaService()
        mocker.patch.object(service.consulta_repo, 'atualizar_status_processando')
        mocker.patch.object(service.consulta_repo, 'adicionar_resultados_ano')
        mocker.patch.object(service.consulta_repo, 'registrar_erro_ano')
        return service
    
    def test_processar_ano_local(self, service, mocker):
        periodo = Mock(mes_inicio=1, mes_fim=12)
        dados_mock = [{"teste": "dados"}]
        
        mocker.patch.object(
            service.optimizer.consulta_local,
            'obter_dados_ano',
            return_value=dados_mock
        )
        
        resultado = service._processar_ano_local(2023, periodo)
        
        assert resultado == dados_mock
        assert len(resultado) == 1
    
    def test_processar_ano_scraper_sucesso(self, service, mocker):
        periodo = Mock(mes_inicio=1, mes_fim=12)
        dados_mock = [{"teste": "dados"}]
        
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = True
        
        mocker.patch.object(
            service.concurrency,
            'get_lock_for_ano',
            return_value=mock_lock
        )
        
        mocker.patch.object(
            service,
            '_executar_scraper_com_retry',
            return_value=dados_mock
        )
        
        resultado = service._processar_ano_scraper("id_teste", 2023, periodo)
        
        assert resultado == dados_mock
        mock_lock.acquire.assert_called_once()
        mock_lock.release.assert_called_once()
    
    def test_processar_ano_scraper_lock_ocupado(self, service, mocker):
        periodo = Mock(mes_inicio=1, mes_fim=12)
        
        mock_lock = MagicMock()
        mock_lock.acquire.return_value = False
        
        mocker.patch.object(
            service.concurrency,
            'get_lock_for_ano',
            return_value=mock_lock
        )
        
        with pytest.raises(Exception, match="já em processamento"):
            service._processar_ano_scraper("id_teste", 2023, periodo)
    
    def test_processar_ano_completo_local(self, service, mocker):
        estrategia = Mock(
            usar_dados_locais=True,
            fonte="local",
            periodo=Mock(mes_inicio=1, mes_fim=12)
        )
        
        dados_mock = [{"teste": "dados"}]
        mocker.patch.object(
            service,
            '_processar_ano_local',
            return_value=dados_mock
        )
        
        service._processar_ano("id_teste", 2023, estrategia, 1, 2)
        
        service.consulta_repo.adicionar_resultados_ano.assert_called_once()
    
    def test_processar_ano_completo_com_erro(self, service, mocker):
        estrategia = Mock(
            usar_dados_locais=False,
            fonte="scraper",
            periodo=Mock(mes_inicio=1, mes_fim=12)
        )
        
        mocker.patch.object(
            service,
            '_processar_ano_scraper',
            side_effect=Exception("Erro teste")
        )
        
        service._processar_ano("id_teste", 2023, estrategia, 1, 1)
        
        service.consulta_repo.registrar_erro_ano.assert_called_once()


class TestConsultaServiceScraperComRetry:
    
    @pytest.fixture
    def service(self, mocker):
        service = ConsultaService()
        mocker.patch.object(service.validator, 'validar_dados_ano')
        mocker.patch.object(service.validator, 'validar_taxa_sucesso', return_value=True)
        return service
    
    def test_executar_scraper_sucesso_primeira_tentativa(self, service, mocker):
        dados_mock = [{"teste": "dados"}]
        dados_validados = [{"teste": "dados", "_ano_validado": 2023}]
        
        mock_scraper = Mock()
        mock_scraper.executar_scraper.return_value = dados_mock
        
        mocker.patch(
            'app.Services.consulta_service.TransparenciaScraper',
            return_value=mock_scraper
        )
        
        service.validator.validar_dados_ano.return_value = dados_validados
        
        resultado = service._executar_scraper_com_retry(2023, 1, 12)
        
        assert resultado == dados_validados
        mock_scraper.executar_scraper.assert_called_once()
    
    def test_executar_scraper_retry_apos_falha(self, service, mocker):
        mock_scraper = Mock()
        mock_scraper.executar_scraper.side_effect = [
            Exception("Primeira falha"),
            [{"teste": "dados"}]
        ]
        
        mocker.patch(
            'app.Services.consulta_service.TransparenciaScraper',
            return_value=mock_scraper
        )
        
        service.validator.validar_dados_ano.return_value = [{"teste": "dados"}]
        
        mocker.patch('time.sleep')
        
        resultado = service._executar_scraper_com_retry(2023, 1, 12, max_retries=2)
        
        assert resultado is not None
        assert mock_scraper.executar_scraper.call_count == 2
    
    def test_executar_scraper_falha_apos_max_retries(self, service, mocker):
        mock_scraper = Mock()
        mock_scraper.executar_scraper.side_effect = Exception("Falha persistente")
        
        mocker.patch(
            'app.Services.consulta_service.TransparenciaScraper',
            return_value=mock_scraper
        )
        
        mocker.patch('time.sleep')
        
        with pytest.raises(Exception, match="Falha persistente"):
            service._executar_scraper_com_retry(2023, 1, 12, max_retries=2)
        
        assert mock_scraper.executar_scraper.call_count == 3
    
    def test_executar_scraper_cancelado_durante_retry(self, service, mocker):
        id_consulta = "id_teste"
        service.consultas_canceladas.add(id_consulta)
        
        with pytest.raises(Exception, match="Consulta cancelada"):
            service._executar_scraper_com_retry(
                2023, 1, 12, 
                id_consulta=id_consulta
            )
    
    def test_executar_scraper_taxa_validade_baixa_retry(self, service, mocker):
        dados_mock = [{"teste": "dados"}] * 10
        dados_validados = [{"teste": "dados"}] * 6
        
        mock_scraper = Mock()
        mock_scraper.executar_scraper.return_value = dados_mock
        
        mocker.patch(
            'app.Services.consulta_service.TransparenciaScraper',
            return_value=mock_scraper
        )
        
        service.validator.validar_dados_ano.return_value = dados_validados
        service.validator.validar_taxa_sucesso.side_effect = [False, True]
        
        mocker.patch('time.sleep')
        
        resultado = service._executar_scraper_com_retry(2023, 1, 12, max_retries=2)
        
        assert resultado == dados_validados
        assert mock_scraper.executar_scraper.call_count == 2


class TestConsultaServiceCancelamento:
    
    @pytest.fixture
    def service(self, mocker):
        service = ConsultaService()
        mocker.patch.object(service.consulta_repo, 'atualizar_status_processando')
        mocker.patch.object(service.consulta_repo, 'finalizar_consulta')
        return service
    
    def test_cancelar_consulta(self, service):
        id_consulta = "id_teste"
        
        resultado = service.cancelar_consulta(id_consulta)
        
        assert id_consulta in service.consultas_canceladas
        assert resultado["status"] == "cancelamento_solicitado"
        service.consulta_repo.atualizar_status_processando.assert_called_once()
    
    def test_verificar_cancelamento_true(self, service):
        id_consulta = "id_teste"
        service.consultas_canceladas.add(id_consulta)
        
        resultado = service._verificar_cancelamento(id_consulta, 2, 5)
        
        assert resultado is True
        service.consulta_repo.finalizar_consulta.assert_called_once_with(
            id_consulta, status="cancelada"
        )
    
    def test_verificar_cancelamento_false(self, service):
        id_consulta = "id_teste"
        
        resultado = service._verificar_cancelamento(id_consulta, 2, 5)
        
        assert resultado is False
        service.consulta_repo.finalizar_consulta.assert_not_called()
    
    def test_finalizar_como_cancelada(self, service):
        id_consulta = "id_teste"
        service.consultas_canceladas.add(id_consulta)
        
        service._finalizar_como_cancelada(id_consulta)
        
        assert id_consulta not in service.consultas_canceladas
        service.consulta_repo.finalizar_consulta.assert_called_once_with(
            id_consulta, status="cancelada"
        )


class TestConsultaServiceConsultas:
    
    @pytest.fixture
    def service(self, mocker):
        service = ConsultaService()
        mocker.patch.object(service.consulta_repo, 'obter_consulta')
        return service
    
    def test_obter_status_consulta(self, service):
        id_consulta = "id_teste"
        dados_mock = {"status": "concluida"}
        
        service.consulta_repo.obter_consulta.return_value = dados_mock
        
        resultado = service.obter_status_consulta(id_consulta)
        
        assert resultado == dados_mock
        service.consulta_repo.obter_consulta.assert_called_once_with(id_consulta)
    
    def test_obter_dados_ano_especifico_sucesso(self, service):
        id_consulta = "id_teste"
        dados_mock = {
            "dados_por_ano": {
                "2023": {
                    "dados": [{"teste": "dados"}],
                    "total_registros": 1
                }
            }
        }
        
        service.consulta_repo.obter_consulta.return_value = dados_mock
        
        resultado = service.obter_dados_ano_especifico(id_consulta, 2023)
        
        assert "ano" in resultado
        assert resultado["ano"] == 2023
        assert "dados" in resultado
    
    def test_obter_dados_ano_especifico_nao_encontrado(self, service):
        id_consulta = "id_teste"
        dados_mock = {"dados_por_ano": {}}
        
        service.consulta_repo.obter_consulta.return_value = dados_mock
        
        resultado = service.obter_dados_ano_especifico(id_consulta, 2023)
        
        assert "error" in resultado
        assert "não encontrados" in resultado["error"]
    
    def test_obter_dados_ano_especifico_consulta_com_erro(self, service):
        id_consulta = "id_teste"
        dados_mock = {"error": "Consulta não encontrada"}
        
        service.consulta_repo.obter_consulta.return_value = dados_mock
        
        resultado = service.obter_dados_ano_especifico(id_consulta, 2023)
        
        assert resultado == dados_mock


class TestConsultaServiceSystemStatus:
    
    def test_get_system_status(self, mocker):
        service = ConsultaService()
        
        status_mock = {
            "max_workers": 8,
            "available_slots": 5,
            "active_threads": 3
        }
        
        mocker.patch.object(
            service.concurrency,
            'get_status',
            return_value=status_mock
        )
        
        resultado = service.get_system_status()
        
        assert resultado == status_mock
        assert "max_workers" in resultado
        assert "available_slots" in resultado


class TestConsultaServiceIntegracao:
    
    @pytest.fixture
    def service(self, mocker):
        service = ConsultaService()
        
        mocker.patch.object(service.consulta_repo, 'iniciar_consulta')
        mocker.patch.object(service.consulta_repo, 'adicionar_metadados_ano')
        mocker.patch.object(service.consulta_repo, 'adicionar_resultados_ano')
        mocker.patch.object(service.consulta_repo, 'finalizar_consulta')
        mocker.patch.object(service.consulta_repo, 'atualizar_status_processando')
        mocker.patch.object(service.consulta_repo, 'registrar_erro_consulta')
        
        return service
    
    def test_executar_consulta_por_anos_completo(self, service, mocker):
        id_consulta = "id_teste"
        
        mock_estrategias = {
            2023: Mock(
                usar_dados_locais=True,
                fonte="local",
                periodo=Mock(mes_inicio=1, mes_fim=12)
            )
        }
        
        mocker.patch.object(
            service.optimizer,
            'definir_estrategia',
            return_value=mock_estrategias
        )
        
        mocker.patch.object(
            service,
            '_processar_ano_local',
            return_value=[{"teste": "dados"}]
        )
        
        service._executar_consulta_por_anos(id_consulta, 2023, 1, 2023, 12)
        
        service.consulta_repo.adicionar_resultados_ano.assert_called_once()
        service.consulta_repo.finalizar_consulta.assert_called_once_with(id_consulta)
    
    def test_executar_consulta_por_anos_com_cancelamento(self, service, mocker):
        id_consulta = "id_teste"
        service.consultas_canceladas.add(id_consulta)
        
        service._executar_consulta_por_anos(id_consulta, 2023, 1, 2023, 12)
        
        service.consulta_repo.finalizar_consulta.assert_called_once_with(
            id_consulta, status="cancelada"
        )
    
    def test_executar_consulta_por_anos_com_erro(self, service, mocker):
        id_consulta = "id_teste"
        
        mocker.patch.object(
            service.optimizer,
            'definir_estrategia',
            side_effect=Exception("Erro no optimizer")
        )
        
        service._executar_consulta_por_anos(id_consulta, 2023, 1, 2023, 12)
        
        service.consulta_repo.registrar_erro_consulta.assert_called_once()


class TestConsultaServiceValidacaoParametros:
    """Testes para validação de parâmetros de entrada."""
    
    @pytest.mark.asyncio
    async def test_processar_consulta_ano_invalido_futuro(self, mocker):
        """Testa rejeição de ano futuro (fora do range 2002-2023)."""
        service = ConsultaService()
        params = ConsultaParams(
            data_inicio="01/2024",  # Ano inválido
            data_fim="12/2024"
        )
        
        background_tasks = BackgroundTasks()
        
        with pytest.raises(ValueError, match="Ano fora do intervalo válido"):
            await service.processar_consulta(params, background_tasks)
    
    @pytest.mark.asyncio
    async def test_processar_consulta_ano_invalido_passado(self, mocker):
        """Testa rejeição de ano muito antigo."""
        service = ConsultaService()
        params = ConsultaParams(
            data_inicio="01/2001",  # Ano inválido
            data_fim="12/2001"
        )
        
        background_tasks = BackgroundTasks()
        
        with pytest.raises(ValueError, match="Ano fora do intervalo válido"):
            await service.processar_consulta(params, background_tasks)