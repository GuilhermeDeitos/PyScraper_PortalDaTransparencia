import pytest
from unittest.mock import Mock, MagicMock, patch
from app.Services.scrapper_service import TransparenciaScraper

class TestTransparenciaScraperUnit:
    """Testes unitários para TransparenciaScraper."""
    
    def test_inicializacao_padrao(self):
        scraper = TransparenciaScraper()
        assert scraper.headless is True
        assert scraper.browser_manager is None
        assert scraper.form_handler is None
    
    def test_inicializacao_headless_false(self):
        scraper = TransparenciaScraper(headless=False)
        assert scraper.headless is False
    
    def test_url_portal_constante(self):
        assert hasattr(TransparenciaScraper, 'URL_PORTAL')
        assert "transparencia.pr.gov.br" in TransparenciaScraper.URL_PORTAL
    
    def test_iniciar_navegador(self, mocker):
        scraper = TransparenciaScraper()
        
        mock_browser_manager = MagicMock()
        mock_driver = Mock()
        mock_browser_manager.iniciar = Mock(return_value=mock_driver)
        
        scraper.browser_manager = mock_browser_manager
        
        with patch("app.Services.scrapper_service.TimerContext"):
            resultado = scraper._iniciar_navegador()
        
        assert resultado == mock_driver
        mock_browser_manager.iniciar.assert_called_once()
    
    def test_acessar_portal(self, mocker):
        scraper = TransparenciaScraper()
        
        mock_driver = MagicMock()
        mock_driver.get = Mock()
        mock_driver.execute_script = Mock(return_value="complete")
        
        mock_browser_manager = MagicMock()
        mock_browser_manager.driver = mock_driver
        
        scraper.browser_manager = mock_browser_manager
        
        mocker.patch("app.Services.scrapper_service.WebDriverWait")
        mocker.patch("time.sleep")
        
        with patch("app.Services.scrapper_service.TimerContext"):
            scraper._acessar_portal()
        
        mock_driver.get.assert_called_once_with(TransparenciaScraper.URL_PORTAL)
    
    def test_executar_pesquisa(self, mocker):
        scraper = TransparenciaScraper()
        mock_driver = Mock()
        
        mock_executar_js = mocker.patch(
            "app.utils.browser_utils.executar_javascript_seguro"
        )
        
        scraper._executar_pesquisa(mock_driver)
        
        mock_executar_js.assert_called_once()
        call_args = mock_executar_js.call_args[0]
        assert "btnPesquisar" in call_args[1]
    
    def test_baixar_dados_sucesso(self, mocker):
        scraper = TransparenciaScraper()
        
        mock_driver = Mock()
        mock_browser_manager = MagicMock()
        mock_browser_manager.download_dir = "/tmp/test"
        mock_browser_manager.scraper_id = "test123"
        
        scraper.browser_manager = mock_browser_manager
        
        dados_mock = [{"coluna1": "valor1"}, {"coluna2": "valor2"}]
        
        mock_baixar = mocker.patch(
            "app.Services.scrapper_service.baixar_e_processar_planilha",
            return_value=dados_mock
        )
        
        with patch("app.Services.scrapper_service.TimerContext"):
            resultado = scraper._baixar_dados(mock_driver)
        
        assert resultado == dados_mock
        assert len(resultado) == 2
        mock_baixar.assert_called_once_with(
            mock_driver,
            "/tmp/test",
            scraper_id="test123"
        )
    
    def test_baixar_dados_vazio_levanta_excecao(self, mocker):
        scraper = TransparenciaScraper()
        
        mock_driver = Mock()
        mock_browser_manager = MagicMock()
        mock_browser_manager.download_dir = "/tmp/test"
        mock_browser_manager.scraper_id = "test123"
        
        scraper.browser_manager = mock_browser_manager
        
        mocker.patch(
            "app.Services.scrapper_service.baixar_e_processar_planilha",
            return_value=[]
        )
        
        with patch("app.Services.scrapper_service.TimerContext"):
            with pytest.raises(Exception, match="Nenhum dado foi extraído"):
                scraper._baixar_dados(mock_driver)
    
    def test_preencher_e_pesquisar(self, mocker):
        scraper = TransparenciaScraper()
        
        mock_driver = Mock()
        mock_browser_manager = MagicMock()
        mock_browser_manager.scraper_id = "test123"
        
        scraper.browser_manager = mock_browser_manager
        
        mock_form_handler = MagicMock()
        mock_form_handler.preencher_pesquisa = Mock()
        
        mocker.patch(
            "app.Services.scrapper_service.FormHandler",
            return_value=mock_form_handler
        )
        
        mocker.patch("app.Services.scrapper_service.TimerContext")
        mocker.patch("time.sleep")
        mocker.patch.object(scraper, '_executar_pesquisa')
        
        scraper._preencher_e_pesquisar(mock_driver, 2023, "JANEIRO", "DEZEMBRO")
        
        mock_form_handler.preencher_pesquisa.assert_called_once_with(
            2023, "JANEIRO", "DEZEMBRO"
        )
        scraper._executar_pesquisa.assert_called_once_with(mock_driver)
    
    def test_executar_scraper_fluxo_completo_mock(self, mocker):
        """Testa o fluxo completo com todos os métodos mockados."""
        scraper = TransparenciaScraper()
        
        # Mock dos métodos internos
        mock_driver = Mock()
        mocker.patch.object(scraper, '_iniciar_navegador', return_value=mock_driver)
        mocker.patch.object(scraper, '_acessar_portal')
        mocker.patch.object(scraper, '_preencher_e_pesquisar')
        mocker.patch.object(
            scraper, 
            '_baixar_dados',
            return_value=[{"teste": "dados"}]
        )
        
        # Mock do BrowserManager com scraper_id como string
        mock_browser_manager = MagicMock()
        mock_browser_manager.scraper_id = "test123"  # String real, não MagicMock
        mock_browser_manager.cleanup = Mock()
        
        mocker.patch(
            "app.Services.scrapper_service.BrowserManager",
            return_value=mock_browser_manager
        )
        
        # Mock do TimerContext para evitar erro de formatação
        mock_timer = MagicMock()
        mock_timer.__enter__ = Mock(return_value=mock_timer)
        mock_timer.__exit__ = Mock(return_value=False)
        mock_timer.get_duration = Mock(return_value=1.234)  # Retorna float
        
        mocker.patch(
            "app.Services.scrapper_service.TimerContext",
            return_value=mock_timer
        )
        
        # Executar
        resultado = scraper.executar_scraper(2023, "JANEIRO", "DEZEMBRO")
        
        # Verificações
        assert len(resultado) == 1
        assert resultado[0]["teste"] == "dados"
        
        scraper._iniciar_navegador.assert_called_once()
        scraper._acessar_portal.assert_called_once()
        scraper._preencher_e_pesquisar.assert_called_once_with(
            mock_driver, 2023, "JANEIRO", "DEZEMBRO"
        )
        scraper._baixar_dados.assert_called_once_with(mock_driver)
        mock_browser_manager.cleanup.assert_called_once()
    
    def test_executar_scraper_erro_e_cleanup(self, mocker):
        """Testa se o cleanup é executado mesmo com erro."""
        from fastapi import HTTPException
        
        scraper = TransparenciaScraper()
        
        mock_browser_manager = MagicMock()
        mock_browser_manager.cleanup = Mock()
        
        mocker.patch(
            "app.Services.scrapper_service.BrowserManager",
            return_value=mock_browser_manager
        )
        
        mocker.patch.object(
            scraper,
            '_iniciar_navegador',
            side_effect=Exception("Erro simulado")
        )
        
        # Mock do TimerContext
        mock_timer = MagicMock()
        mock_timer.__enter__ = Mock(return_value=mock_timer)
        mock_timer.__exit__ = Mock(return_value=False)
        
        mocker.patch(
            "app.Services.scrapper_service.TimerContext",
            return_value=mock_timer
        )
        
        with pytest.raises(HTTPException):
            scraper.executar_scraper(2023, "JANEIRO", "DEZEMBRO")
        
        # Verifica se o cleanup foi chamado mesmo com erro
        mock_browser_manager.cleanup.assert_called_once()