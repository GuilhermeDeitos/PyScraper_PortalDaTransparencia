import pytest
from unittest.mock import Mock, MagicMock, patch
from app.Services.scrapper_service import TransparenciaScraper

class TestTransparenciaScraper:
    
    def test_inicializacao(self):
        scraper = TransparenciaScraper(headless=True)
        assert scraper.headless is True
        assert scraper.browser_manager is None
    
    def test_url_portal_definida(self):
        assert TransparenciaScraper.URL_PORTAL.startswith("https://")
        assert "transparencia.pr.gov.br" in TransparenciaScraper.URL_PORTAL
    
    @pytest.mark.slow
    def test_executar_scraper_com_mock(self, mocker):
        # Mock do BrowserManager
        mock_browser_manager = MagicMock()
        mock_browser_manager.scraper_id = "test123"
        mock_browser_manager.download_dir = "/tmp/test"
        
        # Mock do driver do Selenium
        mock_driver = MagicMock()
        mock_driver.get = Mock()
        mock_driver.execute_script = Mock(return_value="complete")
        
        # Configurar o driver para ser retornado
        mock_browser_manager.driver = mock_driver
        mock_browser_manager.iniciar = Mock(return_value=mock_driver)
        mock_browser_manager.cleanup = Mock()
        
        # Mock do FormHandler
        mock_form_handler = MagicMock()
        mock_form_handler.preencher_pesquisa = Mock()
        
        # Patches necessários
        mocker.patch(
            "app.Services.scrapper_service.BrowserManager",
            return_value=mock_browser_manager
        )
        
        mocker.patch(
            "app.Services.scrapper_service.FormHandler",
            return_value=mock_form_handler
        )
        
        mocker.patch(
            "app.Services.scrapper_service.WebDriverWait"
        )
        
        mocker.patch(
            "app.Services.scrapper_service.baixar_e_processar_planilha",
            return_value=[{"teste": "dados"}]
        )
        
        mocker.patch(
            "app.utils.browser_utils.executar_javascript_seguro"
        )
        
        # Mock do time.sleep para acelerar o teste
        mocker.patch("time.sleep")
        
        # Executar o scraper
        scraper = TransparenciaScraper()
        resultado = scraper.executar_scraper(2023, "JANEIRO", "DEZEMBRO")
        
        # Asserções
        assert len(resultado) == 1
        assert resultado[0]["teste"] == "dados"
        mock_browser_manager.cleanup.assert_called_once()
        mock_driver.get.assert_called_once()
        mock_form_handler.preencher_pesquisa.assert_called_once_with(
            2023, "JANEIRO", "DEZEMBRO"
        )