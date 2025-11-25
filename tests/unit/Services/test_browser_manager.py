import pytest
import os
from unittest.mock import Mock, patch, MagicMock, PropertyMock
from app.Services.browser_manager import BrowserManager

class TestBrowserManager:
    
    def test_inicializacao(self):
        """Testa inicialização básica do BrowserManager."""
        manager = BrowserManager(headless=True)
        assert manager.headless is True
        assert manager.driver is None
        assert len(manager.scraper_id) == 8
    
    def test_inicializacao_com_scraper_id_customizado(self):
        """Testa inicialização com ID customizado."""
        custom_id = "test1234"
        manager = BrowserManager(scraper_id=custom_id)
        assert manager.scraper_id == custom_id
    
    @patch('app.Services.browser_manager.criar_diretorio_download')
    @patch('app.Services.browser_manager.criar_perfil_chrome')
    def test_configurar_opcoes_headless_true(self, mock_perfil, mock_download):
        """Testa configuração de opções com headless ativado."""
        mock_download.return_value = "/tmp/test_download"
        mock_perfil.return_value = "/tmp/test_profile"
        
        manager = BrowserManager(headless=True)
        manager.download_dir = mock_download.return_value
        manager.profile_dir = mock_perfil.return_value
        
        options = manager._configurar_opcoes()
        assert "--headless=new" in options.arguments
        assert "--no-sandbox" in options.arguments
        assert "--disable-dev-shm-usage" in options.arguments
    
    @patch('app.Services.browser_manager.criar_diretorio_download')
    @patch('app.Services.browser_manager.criar_perfil_chrome')
    def test_configurar_opcoes_headless_false(self, mock_perfil, mock_download):
        """Testa configuração de opções com headless desativado."""
        mock_download.return_value = "/tmp/test_download"
        mock_perfil.return_value = "/tmp/test_profile"
        
        manager = BrowserManager(headless=False)
        manager.download_dir = mock_download.return_value
        manager.profile_dir = mock_perfil.return_value
        
        options = manager._configurar_opcoes()
        assert "--headless=new" not in options.arguments
    
    @patch('app.Services.browser_manager.verificar_arquivo_existe')
    def test_configurar_service_com_chromedriver_existente(self, mock_verificar):
        """Testa configuração do service quando ChromeDriver existe."""
        mock_verificar.return_value = True
        
        manager = BrowserManager()
        service = manager._configurar_service()
        
        assert service is not None
        mock_verificar.assert_called_once()
    
    @patch('app.Services.browser_manager.verificar_arquivo_existe')
    def test_configurar_service_sem_chromedriver(self, mock_verificar):
        """Testa configuração do service quando ChromeDriver não existe."""
        mock_verificar.return_value = False
        
        manager = BrowserManager()
        service = manager._configurar_service()
        
        assert service is not None
        mock_verificar.assert_called_once()
    
    @patch('app.Services.browser_manager.remover_diretorio')
    def test_cleanup_sem_driver(self, mock_remover):
        """Testa cleanup quando não há driver ativo."""
        manager = BrowserManager()
        manager.download_dir = "/tmp/test_download"
        manager.profile_dir = "/tmp/test_profile"
        
        manager.cleanup()
        
        assert manager.driver is None
        # Verifica que tentou remover os diretórios
        assert mock_remover.call_count == 2
    
    @patch('app.Services.browser_manager.remover_diretorio')
    def test_cleanup_com_driver(self, mock_remover):
        """Testa cleanup quando há driver ativo."""
        manager = BrowserManager()
        manager.download_dir = "/tmp/test_download"
        manager.profile_dir = "/tmp/test_profile"
        
        # Mock do driver
        mock_driver = Mock()
        manager.driver = mock_driver
        
        manager.cleanup()
        
        # Verifica que tentou fechar o driver
        mock_driver.quit.assert_called_once()
        assert manager.driver is None
    
    def test_get_download_dir(self):
        """Testa getter do diretório de download."""
        manager = BrowserManager()
        manager.download_dir = "/tmp/test_download"
        
        assert manager.get_download_dir() == "/tmp/test_download"
    
    def test_get_profile_dir(self):
        """Testa getter do diretório de perfil."""
        manager = BrowserManager()
        manager.profile_dir = "/tmp/test_profile"
        
        assert manager.get_profile_dir() == "/tmp/test_profile"
    
    def test_is_alive_sem_driver(self):
        """Testa is_alive quando não há driver."""
        manager = BrowserManager()
        assert manager.is_alive() is False
    
    def test_is_alive_com_driver_ativo(self):
        """Testa is_alive com driver ativo."""
        manager = BrowserManager()
        mock_driver = Mock()
        mock_driver.current_url = "http://test.com"
        manager.driver = mock_driver
        
        assert manager.is_alive() is True
    
    def test_is_alive_com_driver_inativo(self):
        """Testa is_alive com driver inativo (lança exceção ao acessar current_url)."""
        manager = BrowserManager()
        mock_driver = Mock()
        
        # Usar PropertyMock para que current_url lance exceção ao ser acessado
        type(mock_driver).current_url = PropertyMock(side_effect=Exception("Driver morto"))
        manager.driver = mock_driver
        
        assert manager.is_alive() is False
    
    def test_configurar_timeouts(self):
        """Testa configuração de timeouts."""
        manager = BrowserManager()
        mock_driver = Mock()
        manager.driver = mock_driver
        
        manager._configurar_timeouts()
        
        mock_driver.implicitly_wait.assert_called_once_with(10)
        mock_driver.set_page_load_timeout.assert_called_once_with(60)
        mock_driver.set_script_timeout.assert_called_once_with(30)
    
    def test_cleanup_com_erro_ao_fechar_driver(self):
        """Testa cleanup quando ocorre erro ao fechar o driver."""
        manager = BrowserManager()
        manager.download_dir = "/tmp/test_download"
        manager.profile_dir = "/tmp/test_profile"
        
        mock_driver = Mock()
        mock_driver.quit.side_effect = Exception("Erro ao fechar")
        manager.driver = mock_driver
        
        # Não deve lançar exceção
        with patch('app.Services.browser_manager.remover_diretorio') as mock_remover:
            mock_remover.return_value = True
            manager.cleanup()
        
        # Driver deve ser None mesmo com erro
        assert manager.driver is None
    
    @patch('app.Services.browser_manager.criar_diretorio_download')
    @patch('app.Services.browser_manager.criar_perfil_chrome')
    def test_configurar_opcoes_inclui_diretorio_download(self, mock_perfil, mock_download):
        """Testa que as opções incluem o diretório de download correto."""
        mock_download.return_value = "/tmp/test_download_custom"
        mock_perfil.return_value = "/tmp/test_profile_custom"
        
        manager = BrowserManager(headless=True)
        manager.download_dir = mock_download.return_value
        manager.profile_dir = mock_perfil.return_value
        
        options = manager._configurar_opcoes()
        
        # Verificar que as preferências incluem o diretório correto
        prefs = options.experimental_options.get('prefs', {})
        assert prefs.get('download.default_directory') == "/tmp/test_download_custom"
    
    @patch('app.Services.browser_manager.criar_diretorio_download')
    @patch('app.Services.browser_manager.criar_perfil_chrome')
    def test_configurar_opcoes_inclui_user_data_dir(self, mock_perfil, mock_download):
        """Testa que as opções incluem o user-data-dir correto."""
        mock_download.return_value = "/tmp/test_download"
        mock_perfil.return_value = "/tmp/test_profile_unique"
        
        manager = BrowserManager(headless=True)
        manager.download_dir = mock_download.return_value
        manager.profile_dir = mock_perfil.return_value
        
        options = manager._configurar_opcoes()
        
        # Verificar que user-data-dir está nos argumentos
        user_data_arg = f"--user-data-dir={mock_perfil.return_value}"
        assert user_data_arg in options.arguments