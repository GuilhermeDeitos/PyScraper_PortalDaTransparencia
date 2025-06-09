"""
Utilitários para configuração e manipulação do navegador Selenium.
"""
import os
import time
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import Optional

logger = logging.getLogger(__name__)

def configurar_chrome_options(headless: bool = True, download_dir: Optional[str] = None) -> Options:
    """
    Configura as opções do Chrome para o scraper.
    
    Args:
        headless: Se True, executa o navegador em modo headless
        download_dir: Diretório para download de arquivos
        
    Returns:
        Objeto Options configurado
    """
    chrome_options = Options()
    
    if headless:
        chrome_options.add_argument("--headless")
    
    # Configurações básicas
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-background-networking")
    chrome_options.add_argument("--disable-sync")
    chrome_options.add_argument("--metrics-recording-only")
    chrome_options.add_argument("--disable-default-apps")
    chrome_options.add_argument("--mute-audio")
    chrome_options.add_argument("--disable-gl-drawing-for-tests")
    chrome_options.add_argument("--ignore-gpu-blocklist")
    chrome_options.add_argument("--window-size=1920,1080")
    
    # Configuração de diretório de download
    if download_dir:
        prefs = {
            "download.default_directory": download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False
        }
        chrome_options.add_experimental_option("prefs", prefs)
    
    logger.debug(f"Chrome options configuradas: headless={headless}, download_dir={download_dir}")
    return chrome_options

def iniciar_navegador(headless: bool = True, download_dir: Optional[str] = None) -> webdriver.Chrome:
    """
    Inicia o navegador Chrome com as opções configuradas.
    
    Args:
        headless: Se True, executa o navegador em modo headless
        download_dir: Diretório para download de arquivos
        
    Returns:
        Instância do WebDriver
    """
    chrome_options = configurar_chrome_options(headless, download_dir)
    
    try:
        service = Service(relative_path='../chromedriver.exe')
        driver = webdriver.Chrome(options=chrome_options, service=service)
        logger.info("Navegador Chrome iniciado com sucesso")
        return driver
    except Exception as e:
        logger.error(f"Erro ao iniciar navegador: {e}")
        raise

def esperar_download_completo(diretorio: str, timeout: int = 60) -> bool:
    """
    Aguarda a conclusão de um download no diretório especificado.
    
    Args:
        diretorio: Diretório onde o arquivo está sendo baixado
        timeout: Tempo máximo de espera em segundos
        
    Returns:
        True se o download foi concluído, False se o timeout foi atingido
    """
    tempo_inicio = time.time()
    
    while time.time() - tempo_inicio < timeout:
        # Verifica se há arquivos temporários de download
        arquivos_temp = [f for f in os.listdir(diretorio) if f.endswith('.crdownload') or f.endswith('.tmp')]
        
        if not arquivos_temp:
            # Verifica se há pelo menos um arquivo no diretório
            arquivos = [f for f in os.listdir(diretorio) if os.path.isfile(os.path.join(diretorio, f))]
            if arquivos:
                logger.info(f"Download concluído em {time.time() - tempo_inicio:.2f} segundos")
                return True
        
        # Aguarda um pouco antes de verificar novamente
        time.sleep(0.5)
    
    logger.warning(f"Timeout atingido após {timeout} segundos")
    return False

def executar_javascript_seguro(driver: webdriver.Chrome, script: str) -> Optional[any]:
    """
    Executa um script JavaScript com tratamento de erros.
    
    Args:
        driver: Instância do WebDriver
        script: Script JavaScript a ser executado
        
    Returns:
        Resultado da execução do script, ou None em caso de erro
    """
    try:
        resultado = driver.execute_script(script)
        return resultado
    except Exception as e:
        logger.error(f"Erro ao executar JavaScript: {e}")
        logger.debug(f"Script que falhou: {script}")
        return None