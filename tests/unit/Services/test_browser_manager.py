import pytest
import os
from app.Services.browser_manager import BrowserManager

class TestBrowserManager:
    
    def test_inicializacao(self):
        manager = BrowserManager(headless=True)
        assert manager.headless is True
        assert manager.driver is None
        assert len(manager.scraper_id) == 8
    
    def test_criar_diretorio_download(self):
        manager = BrowserManager()
        download_dir = manager._criar_diretorio_download()
        
        assert os.path.exists(download_dir)
        assert manager.scraper_id in download_dir
        
        manager.download_dir = download_dir
        manager.cleanup()
    
    def test_criar_perfil_chrome(self):
        manager = BrowserManager()
        profile_dir = manager._criar_perfil_chrome()
        
        assert os.path.exists(profile_dir)
        assert "chrome_profile_" in profile_dir
        
        manager.profile_dir = profile_dir
        manager.cleanup()
    
    def test_configurar_opcoes_headless_true(self):
        manager = BrowserManager(headless=True)
        manager.download_dir = "/tmp/test"
        manager.profile_dir = "/tmp/profile"
        
        options = manager._configurar_opcoes()
        assert "--headless=new" in options.arguments
    
    def test_configurar_opcoes_headless_false(self):
        manager = BrowserManager(headless=False)
        manager.download_dir = "/tmp/test"
        manager.profile_dir = "/tmp/profile"
        
        options = manager._configurar_opcoes()
        assert "--headless=new" not in options.arguments
    
    def test_cleanup_sem_driver(self):
        manager = BrowserManager()
        manager.cleanup()
        assert manager.driver is None