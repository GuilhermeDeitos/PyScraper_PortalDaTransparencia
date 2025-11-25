import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from typing import Optional
import uuid
import random
import os
from app.utils.file_utils import (
    criar_diretorio_download,
    criar_perfil_chrome,
    remover_diretorio,
    verificar_arquivo_existe
)

logger = logging.getLogger(__name__)

class BrowserManager:
    """Gerencia ciclo de vida do navegador Chrome."""
    
    def __init__(self, headless: bool = True, scraper_id: Optional[str] = None):
        """
        Inicializa o gerenciador de navegador.
        
        Args:
            headless: Se True, executa Chrome em modo headless
            scraper_id: ID único para este scraper (gerado automaticamente se não fornecido)
        """
        self.headless = headless
        self.scraper_id = scraper_id or str(uuid.uuid4())[:8]
        self.driver: Optional[webdriver.Chrome] = None
        self.download_dir: Optional[str] = None
        self.profile_dir: Optional[str] = None
    
    def iniciar(self) -> webdriver.Chrome:
        """
        Inicia o navegador e retorna a instância.
        
        Returns:
            Instância do WebDriver do Chrome
            
        Raises:
            Exception: Se falhar ao iniciar o navegador
        """
        # Criar diretórios usando utilitários centralizados
        self.download_dir = criar_diretorio_download(self.scraper_id)
        self.profile_dir = criar_perfil_chrome(self.scraper_id)
        
        options = self._configurar_opcoes()
        service = self._configurar_service()
        
        try:
            self.driver = webdriver.Chrome(service=service, options=options)
            self._configurar_timeouts()
            
            # Log de informações do navegador
            logger.info(f"[Browser {self.scraper_id}] Iniciado com sucesso")
            logger.info(
                f"[Browser {self.scraper_id}] Chrome version: "
                f"{self.driver.capabilities.get('browserVersion', 'unknown')}"
            )
            logger.info(
                f"[Browser {self.scraper_id}] ChromeDriver version: "
                f"{self.driver.capabilities.get('chrome', {}).get('chromedriverVersion', 'unknown')}"
            )
            
            return self.driver
            
        except Exception as e:
            logger.error(f"[Browser {self.scraper_id}] Erro ao iniciar navegador: {e}")
            self.cleanup()
            raise
    
    def _configurar_service(self) -> Service:
        """
        Configura o Service do ChromeDriver.
        
        Returns:
            Instância configurada do Service
        """
        chromedriver_path = os.getenv('CHROMEDRIVER_BIN', '/usr/local/bin/chromedriver')
        
        if not verificar_arquivo_existe(chromedriver_path):
            logger.warning(
                f"ChromeDriver não encontrado em {chromedriver_path}, "
                "usando padrão do sistema"
            )
            return Service()  # Deixa Selenium encontrar automaticamente
        
        logger.info(f"[Browser {self.scraper_id}] Usando ChromeDriver: {chromedriver_path}")
        return Service(executable_path=chromedriver_path)
    
    def _configurar_opcoes(self) -> Options:
        """
        Configura opções do Chrome para execução.
        
        Returns:
            Instância configurada de Options
        """
        options = Options()
        
        # Chrome binary path
        chrome_bin = os.getenv('CHROME_BIN', '/usr/bin/google-chrome')
        if verificar_arquivo_existe(chrome_bin):
            options.binary_location = chrome_bin
            logger.info(f"[Browser {self.scraper_id}] Chrome binary: {chrome_bin}")
        else:
            logger.warning(f"[Browser {self.scraper_id}] Chrome binary não encontrado: {chrome_bin}")
        
        # Modo headless
        if self.headless:
            options.add_argument("--headless=new")
            logger.info(f"[Browser {self.scraper_id}] Modo headless ativado")
        
        # Argumentos essenciais para container/servidor
        essential_args = [
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
            "--disable-software-rasterizer",
            "--disable-extensions",
            "--disable-setuid-sandbox",
        ]
        
        for arg in essential_args:
            options.add_argument(arg)
        
        # Perfil e debugging
        options.add_argument(f"--user-data-dir={self.profile_dir}")
        debug_port = 9222 + random.randint(0, 1000)
        options.add_argument(f"--remote-debugging-port={debug_port}")
        
        # Window size para screenshots
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--start-maximized")
        
        # Preferências de download
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False,
            "profile.default_content_settings.popups": 0,
        }
        options.add_experimental_option("prefs", prefs)
        
        # Opções experimentais para evitar detecção
        options.add_experimental_option(
            "excludeSwitches", 
            ["enable-logging", "enable-automation"]
        )
        options.add_experimental_option("useAutomationExtension", False)
        
        return options
    
    def _configurar_timeouts(self) -> None:
        """Configura timeouts do WebDriver."""
        if self.driver:
            self.driver.implicitly_wait(10)
            self.driver.set_page_load_timeout(60)
            self.driver.set_script_timeout(30)
            logger.debug(f"[Browser {self.scraper_id}] Timeouts configurados")
    
    def cleanup(self) -> None:
        """
        Limpa recursos do navegador e diretórios temporários.
        Chamado automaticamente ao finalizar ou em caso de erro.
        """
        # Fechar navegador
        if self.driver:
            try:
                self.driver.quit()
                logger.info(f"[Browser {self.scraper_id}] Navegador fechado")
            except Exception as e:
                logger.warning(f"[Browser {self.scraper_id}] Erro ao fechar navegador: {e}")
            finally:
                self.driver = None
        
        # Limpar diretório de download
        if self.download_dir:
            if remover_diretorio(self.download_dir, forcar=True):
                logger.info(f"[Browser {self.scraper_id}] Download dir removido: {self.download_dir}")
            else:
                logger.warning(
                    f"[Browser {self.scraper_id}] "
                    f"Não foi possível remover download dir: {self.download_dir}"
                )
        
        # Limpar diretório de perfil
        if self.profile_dir:
            if remover_diretorio(self.profile_dir, forcar=True):
                logger.info(f"[Browser {self.scraper_id}] Profile dir removido: {self.profile_dir}")
            else:
                logger.warning(
                    f"[Browser {self.scraper_id}] "
                    f"Não foi possível remover profile dir: {self.profile_dir}"
                )
    
    def get_download_dir(self) -> Optional[str]:
        """Retorna o diretório de downloads."""
        return self.download_dir
    
    def get_profile_dir(self) -> Optional[str]:
        """Retorna o diretório de perfil."""
        return self.profile_dir
    
    def is_alive(self) -> bool:
        """Verifica se o navegador está ativo."""
        if not self.driver:
            return False
        
        try:
            # Tenta obter URL atual como verificação de vida
            _ = self.driver.current_url
            return True
        except Exception:
            return False