import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from typing import Optional
import uuid
import random
import tempfile
import os
from app.utils.file_utils import criar_diretorio_temporario, remover_diretorio

logger = logging.getLogger(__name__)

class BrowserManager:
    """Gerencia ciclo de vida do navegador Chrome."""
    
    def __init__(self, headless: bool = True, scraper_id: str = None):
        self.headless = headless
        self.scraper_id = scraper_id or str(uuid.uuid4())[:8]
        self.driver: Optional[webdriver.Chrome] = None
        self.download_dir: Optional[str] = None
        self.profile_dir: Optional[str] = None
    
    def iniciar(self) -> webdriver.Chrome:
        """Inicia o navegador e retorna a instância."""
        self.download_dir = self._criar_diretorio_download()
        self.profile_dir = self._criar_perfil_chrome()
        
        options = self._configurar_opcoes()
        
        try:
            self.driver = webdriver.Chrome(options=options)
            self._configurar_timeouts()
            logger.info(f"[Browser {self.scraper_id}] Iniciado com sucesso")
            return self.driver
        except Exception as e:
            self.cleanup()
            raise
    
    def _criar_diretorio_download(self) -> str:
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        dir_name = f"downloads_{self.scraper_id}_{timestamp}"
        return criar_diretorio_temporario(subdir=dir_name)
    
    def _criar_perfil_chrome(self) -> str:
        profile_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_{self.scraper_id}")
        os.makedirs(profile_dir, exist_ok=True)
        return profile_dir
    
    def _configurar_opcoes(self) -> Options:
        options = Options()
        
        if self.headless:
            options.add_argument("--headless=new")
        
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        options.add_argument(f"--remote-debugging-port={9222 + random.randint(0, 1000)}")
        
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "safebrowsing.enabled": False,
        }
        options.add_experimental_option("prefs", prefs)
        
        return options
    
    def _configurar_timeouts(self):
        if self.driver:
            self.driver.implicitly_wait(10)
            self.driver.set_page_load_timeout(60)
            self.driver.set_script_timeout(30)
    
    def cleanup(self):
        """Limpa recursos do navegador."""
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning(f"[Browser {self.scraper_id}] Erro ao fechar: {e}")
            finally:
                self.driver = None
        
        if self.download_dir and os.path.exists(self.download_dir):
            remover_diretorio(self.download_dir)
        
        if self.profile_dir and os.path.exists(self.profile_dir):
            remover_diretorio(self.profile_dir)