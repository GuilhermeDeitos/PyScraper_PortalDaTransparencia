import logging
import time
from typing import List, Dict, Any
from fastapi import HTTPException
from selenium.webdriver.support.ui import WebDriverWait

from app.Services.browser_manager import BrowserManager
from app.Services.form_handler import FormHandler
from app.utils.planilha import baixar_e_processar_planilha
from app.utils.performance_tracker import TimerContext

logger = logging.getLogger(__name__)

class TransparenciaScraper:
    """Classe para extrair dados do Portal da Transparência do Paraná."""
    
    URL_PORTAL = "https://www.transparencia.pr.gov.br/pte/assunto/4/22?origem=3"
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.browser_manager = None
        self.form_handler = None
    
    def executar_scraper(self, ano: int, mes_inicio: str, mes_fim: str) -> List[Dict[str, Any]]:
        """
        Executa o scraper para coletar dados do Portal da Transparência.
        
        Args:
            ano: Ano para coleta
            mes_inicio: Mês inicial
            mes_fim: Mês final
            
        Returns:
            Lista de dicionários com os dados coletados
        """
        self.browser_manager = BrowserManager(headless=self.headless)
        
        try:
            with TimerContext("total_scraper") as timer_total:
                driver = self._iniciar_navegador()
                self._acessar_portal()
                self._preencher_e_pesquisar(driver, ano, mes_inicio, mes_fim)
                dados = self._baixar_dados(driver)
            
            logger.info(f"[Scraper {self.browser_manager.scraper_id}] "
                       f"Concluído em {timer_total.get_duration():.2f}s")
            return dados
            
        except Exception as e:
            logger.error(f"Erro no scraper: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
        finally:
            if self.browser_manager:
                self.browser_manager.cleanup()
    
    def _iniciar_navegador(self):
        with TimerContext("iniciar_navegador"):
            return self.browser_manager.iniciar()
    
    def _acessar_portal(self):
        with TimerContext("acessar_portal"):
            driver = self.browser_manager.driver
            logger.info(f"Acessando: {self.URL_PORTAL}")
            driver.get(self.URL_PORTAL)
            
            WebDriverWait(driver, 20).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(2)
    
    def _preencher_e_pesquisar(self, driver, ano: int, mes_inicio: str, mes_fim: str):
        self.form_handler = FormHandler(driver, self.browser_manager.scraper_id)
        
        with TimerContext("preencher_formulario"):
            self.form_handler.preencher_pesquisa(ano, mes_inicio, mes_fim)
            time.sleep(2)
        
        with TimerContext("executar_pesquisa"):
            self._executar_pesquisa(driver)
            time.sleep(3)
    
    def _executar_pesquisa(self, driver):
        """Executa a pesquisa após preencher o formulário."""
        from app.utils.browser_utils import executar_javascript_seguro
        
        logger.info("Executando pesquisa...")
        executar_javascript_seguro(
            driver,
            "PrimeFaces.ab({s:'formPesquisaDespesa:btnPesquisar'});"
        )
    
    def _baixar_dados(self, driver) -> List[Dict[str, Any]]:
        with TimerContext("baixar_processar_planilha"):
            dados = baixar_e_processar_planilha(
                driver,
                self.browser_manager.download_dir,
                scraper_id=self.browser_manager.scraper_id
            )
            
            if not dados:
                raise Exception("Nenhum dado foi extraído da planilha")
            
            return dados