import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import Select
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from fastapi import HTTPException
from app.utils.planilha import baixar_e_processar_planilha
from app.utils.browser_utils import iniciar_navegador, executar_javascript_seguro
from app.utils.file_utils import criar_diretorio_temporario, remover_diretorio
from app.utils.performance_tracker import TimerContext
import logging
import time
from typing import List, Dict, Any, Tuple, Callable, Optional
import os
import uuid
from datetime import datetime
import random
import tempfile

# Configuração de logging
logger = logging.getLogger(__name__)

# Lock global para garantir criação segura de diretórios
DIRECTORY_CREATION_LOCK = threading.Lock()

class TransparenciaScraper:
    """Classe para extrair dados do Portal da Transparência do Paraná."""
    
    def __init__(self, headless: bool = True):
        """
        Inicializa o scraper.
        
        Args:
            headless: Se True, executa o navegador em modo headless.
        """
        self.headless = headless
        self.driver = None
        self.download_dir = None
        # ID único para esta instância do scraper
        self.scraper_id = str(uuid.uuid4())[:8]
        self.thread_id = threading.get_ident()
        logger.info(f"Criando scraper {self.scraper_id} na thread {self.thread_id}")
    
    def _iniciar_navegador(self) -> None:
        """Inicia o navegador Chrome com as opções configuradas."""
        with DIRECTORY_CREATION_LOCK:
            # Criar diretório único para cada thread/scraper
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            dir_name = f"downloads_{self.scraper_id}_{timestamp}_{self.thread_id}"
            
            logger.info(f"[Scraper {self.scraper_id}] Criando diretório temporário isolado: {dir_name}")
            self.download_dir = criar_diretorio_temporario(subdir=dir_name)
        
        logger.info(f"[Scraper {self.scraper_id}] Iniciando navegador Chrome isolado...")
        
        # Adicionar mais isolamento nas opções do Chrome
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")  # Novo modo headless
        
        # Opções para melhor isolamento entre instâncias
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-plugins")
        chrome_options.add_argument("--disable-images")
        chrome_options.add_argument("--disable-javascript-harmony-shipping")
        
        # Criar diretório de perfil único para cada instância
        profile_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_{self.scraper_id}")
        chrome_options.add_argument(f"--user-data-dir={profile_dir}")
        
        # Adicionar um port único para cada instância
        port = 9222 + random.randint(0, 1000)
        chrome_options.add_argument(f"--remote-debugging-port={port}")
        
        # Configurações de download específicas
        prefs = {
            "download.default_directory": self.download_dir,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": False,
            "profile.default_content_setting_values.automatic_downloads": 1,
            "profile.default_content_settings.popups": 0,
            "profile.managed_user_id": self.scraper_id,
            "profile.content_settings.exceptions.automatic_downloads.*.setting": 1
        }
        chrome_options.add_experimental_option("prefs", prefs)
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        
        # Configurar capacidades desejadas
        chrome_options.set_capability("acceptInsecureCerts", True)
        chrome_options.set_capability("pageLoadStrategy", "normal")
        
        try:
            self.driver = webdriver.Chrome(options=chrome_options)
            
            # Configurar timeouts
            self.driver.implicitly_wait(10)
            self.driver.set_page_load_timeout(60)
            self.driver.set_script_timeout(30)
            
            # Verificar e configurar o diretório de download após inicialização
            self.driver.execute_script(f"""
                if (window.chrome && window.chrome.downloads) {{
                    chrome.downloads.setShelfEnabled(false);
                }}
            """)
            
            logger.info(f"[Scraper {self.scraper_id}] Navegador iniciado com sucesso (porta: {port})")
            
        except Exception as e:
            logger.error(f"[Scraper {self.scraper_id}] Erro ao iniciar navegador: {e}")
            # Limpar diretório de perfil em caso de erro
            if os.path.exists(profile_dir):
                try:
                    remover_diretorio(profile_dir)
                except:
                    pass
            raise
    
    def _interagir_com_elemento(self, estrategias: List[Tuple[str, Callable]], mensagem_erro: str = "Erro ao interagir com elemento") -> Any:
        """
        Tenta múltiplas estratégias para interagir com um elemento.
        
        Args:
            estrategias: Lista de tuplas (descrição, função) com as estratégias a tentar.
            mensagem_erro: Mensagem de erro caso todas as estratégias falhem.
            
        Returns:
            O resultado da primeira estratégia bem-sucedida.
            
        Raises:
            Exception: Se todas as estratégias falharem.
        """
        last_error = None
        for i, (descricao, funcao) in enumerate(estrategias):
            try:
                logger.debug(f"Tentando abordagem {i+1}: {descricao}")
                resultado = funcao()
                logger.debug(f"Abordagem {i+1} bem-sucedida!")
                return resultado
            except Exception as e:
                logger.debug(f"Falha na abordagem {i+1}: {str(e)}")
                last_error = e
        
        # Se chegou aqui, todas as abordagens falharam
        raise Exception(f"{mensagem_erro}: {str(last_error)}")
    
    def _preencher_formulario(self, ano: int, mes_inicio: str, mes_fim: str) -> None:
        """
        Preenche o formulário de pesquisa com os parâmetros especificados.
        
        Args:
            ano: Ano para o qual os dados serão coletados.
            mes_inicio: Mês inicial para a coleta de dados.
            mes_fim: Mês final para a coleta de dados.
        """
        logger.info("Preenchendo formulário de pesquisa...")
        
        # ----- CAMPO ANO -----
        logger.info(f"Configurando campo de ano: {ano}")
        executar_javascript_seguro(self.driver, 
            f"document.getElementById('formPesquisaDespesa:filtroAno_input').value = '{ano}'; "
            f"PrimeFaces.ab({{s:'formPesquisaDespesa:filtroAno',e:'change'}});"
        )
        
        # ----- CAMPO MÊS INICIAL -----
        logger.info(f"Configurando mês inicial: {mes_inicio}")
        executar_javascript_seguro(self.driver,
            f"document.getElementById('formPesquisaDespesa:filtroMesInicio_input').value = '{mes_inicio}'; "
            f"PrimeFaces.ab({{s:'formPesquisaDespesa:filtroMesInicio',e:'change'}});"
        )
        
        # ----- CAMPO MÊS FINAL -----
        logger.info(f"Configurando mês final: {mes_fim}")
        executar_javascript_seguro(self.driver,
            f"document.getElementById('formPesquisaDespesa:filtroMesTermino_input').value = '{mes_fim}'; "
            f"PrimeFaces.ab({{s:'formPesquisaDespesa:filtroMesTermino',e:'change'}});"
        )
        
        # ----- CAMPO ÓRGÃO -----
        logger.info("Configurando campo de órgão...")
        orgao_desejado = "45" 
        orgao_value = "UniqueKey[codigo=45, exercicio=2023]"
        executar_javascript_seguro(self.driver,
            f"var select = document.getElementById('formPesquisaDespesa:filtroOrgao_input'); "
            f"select.value = '{orgao_value}'; "
            f"PrimeFaces.ab({{s:'formPesquisaDespesa:filtroOrgao',e:'change',p:'formPesquisaDespesa:painelFiltro',u:'formPesquisaDespesa:painelFiltro',onco:function(xhr,status,args){{iniciarPopover();}}}});"
        )
        logger.info(f"Órgão selecionado: {orgao_desejado}")
        
        # ----- CHECKBOXES -----
        self._marcar_checkbox('formPesquisaDespesa:detalheFiltroUnidadeOrcamentaria', "unidades orçamentárias")
        self._marcar_checkbox('formPesquisaDespesa:detalheFiltroFuncao', "funções")
        self._marcar_checkbox('formPesquisaDespesa:detalheFiltroOrigemRecursos', "origens de recursos")
        self._marcar_checkbox('formPesquisaDespesa:detalhFiltroGrupoDespesaNatureza', "grupos de natureza de despesa")

    def _tirar_screenshot(self, nome_arquivo: str) -> None:
        """
        Tira uma screenshot da página atual.
        
        Args:
            nome_arquivo: Nome do arquivo onde a screenshot será salva.
        """
        logger.info(f"Tirando screenshot: {nome_arquivo}")
        self.driver.save_screenshot(nome_arquivo)

    def _marcar_checkbox(self, id_base: str, descricao: str) -> None:
        """
        Marca um checkbox PrimeFaces usando JavaScript.
        
        Args:
            id_base: ID base do checkbox sem o sufixo '_input'.
            descricao: Descrição do checkbox para logging.
        """
        logger.info(f"Marcando checkbox de {descricao}...")
        
        # Abordagem mais robusta usando apenas JavaScript e IDs, sem querySelector
        executar_javascript_seguro(self.driver, f"""
            // Marca o checkbox diretamente pelo ID
            var input = document.getElementById('{id_base}_input');
            input.checked = true;
            
            // Dispara evento de change para atualizar o estado visual
            var event = new Event('change', {{ bubbles: true }});
            input.dispatchEvent(event);
            
            // Dispara o evento para o PrimeFaces
            PrimeFaces.ab({{s:'{id_base}', e:'change'}});
            
            // Atualiza também a parte visual manualmente
            var checkboxContainer = document.getElementById('{id_base}');
            if (checkboxContainer) {{
                var boxElements = checkboxContainer.getElementsByClassName('ui-chkbox-box');
                if (boxElements.length > 0) {{
                    var boxElement = boxElements[0];
                    boxElement.classList.remove('ui-state-default');
                    boxElement.classList.add('ui-state-active');
                    
                    var iconElements = boxElement.getElementsByClassName('ui-chkbox-icon');
                    if (iconElements.length > 0) {{
                        var iconElement = iconElements[0];
                        iconElement.classList.remove('ui-icon-blank');
                        iconElement.classList.add('ui-icon-check');
                    }}
                }}
            }}
        """)
        
        # Verificar se o checkbox foi marcado
        is_checked = executar_javascript_seguro(self.driver, f"return document.getElementById('{id_base}_input').checked;")
        logger.info(f"Checkbox de {descricao} marcado: {is_checked}")
    
    def _clicar_botao_pesquisa(self) -> None:
        """
        Clica no botão de pesquisa e aguarda o carregamento dos resultados.
        Lida com possíveis overlays que possam estar bloqueando o botão.
        """
        logger.info("Preparando para clicar no botão de pesquisa...")
        
        # Tentativa 1: Remover qualquer overlay que possa estar bloqueando
        try:
            executar_javascript_seguro(self.driver, """
                // Remove qualquer overlay que possa estar bloqueando
                var overlays = document.querySelectorAll('.ui-widget-overlay');
                overlays.forEach(function(overlay) {
                    overlay.parentNode.removeChild(overlay);
                });
                
                // Remove quaisquer modais ativos
                var modals = document.querySelectorAll('.ui-dialog');
                modals.forEach(function(modal) {
                    modal.parentNode.removeChild(modal);
                });
            """)
            logger.info("Overlays e modais removidos via JavaScript")
        except Exception as e:
            logger.warning(f"Erro ao remover overlays: {e}")
        
        # Pausa para garantir que as alterações de DOM tenham efeito
        time.sleep(2)
        
        # Tentativa 2: Usar JavaScript para clicar no botão diretamente (mais confiável)
        try:
            logger.info("Tentando clicar no botão via JavaScript...")
            executar_javascript_seguro(self.driver, """
                // Abordagem 1: Usar o evento PrimeFaces diretamente
                PrimeFaces.ab({
                    s: 'formPesquisaDespesa:btnPesquisar',
                    p: 'formPesquisaDespesa',
                    u: 'formPesquisaDespesa',
                    onco: function(xhr, status, args) { iniciarPopover(); }
                });
            """)
            logger.info("Botão clicado via JavaScript PrimeFaces.ab()")
        except Exception as e:
            logger.warning(f"Falha ao clicar via PrimeFaces.ab(): {e}")
            
            try:
                # Abordagem alternativa: simular clique via JavaScript
                executar_javascript_seguro(self.driver, """
                    document.getElementById('formPesquisaDespesa:btnPesquisar').click();
                """)
                logger.info("Botão clicado via JavaScript element.click()")
            except Exception as e2:
                logger.warning(f"Falha ao clicar via JavaScript element.click(): {e2}")
                
                # Última tentativa: Selenium nativo com tratamento de exceções
                try:
                    # Tentar via selenium com WebDriverWait
                    botao = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.NAME, 'formPesquisaDespesa:btnPesquisar'))
                    )
                    # Scroll até o botão para garantir visibilidade
                    executar_javascript_seguro(self.driver, "arguments[0].scrollIntoView(true);", botao)
                    time.sleep(1)
                    botao.click()
                    logger.info("Botão clicado via Selenium após espera e scroll")
                except Exception as e3:
                    logger.error(f"Todas as tentativas de clicar no botão falharam: {e3}")
                    raise
        
        # Aguarda carregamento dos resultados
        logger.info("Aguardando carregamento dos resultados...")
        time.sleep(5)
        
        # Verificar se a pesquisa foi bem-sucedida
        try:
            # Verifica se algum elemento de resultado apareceu
            resultados_visiveis = executar_javascript_seguro(self.driver, """
                return document.querySelectorAll('table[id$="tabResultados"] tbody tr').length > 0;
            """)
            if resultados_visiveis:
                logger.info("Resultados carregados com sucesso")
            else:
                logger.warning("Nenhum resultado visível após a pesquisa")
        except Exception as e:
            logger.warning(f"Não foi possível verificar os resultados: {e}")
            
            
    def __del__(self):
        """Destrutor para garantir limpeza de recursos"""
        self.cleanup()
    
    def cleanup(self):
        """Limpa recursos do scraper"""
        try:
            if self.driver:
                logger.info(f"[Scraper {self.scraper_id}] Fechando navegador...")
                try:
                    # Limpar cookies e storage antes de fechar
                    self.driver.execute_script("window.localStorage.clear();")
                    self.driver.execute_script("window.sessionStorage.clear();")
                    self.driver.delete_all_cookies()
                except:
                    pass
                    
                self.driver.quit()
                self.driver = None
                
            if self.download_dir and os.path.exists(self.download_dir):
                logger.info(f"[Scraper {self.scraper_id}] Limpando diretório: {self.download_dir}")
                remover_diretorio(self.download_dir)
                self.download_dir = None
                
            # Limpar diretório de perfil do Chrome
            profile_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_{self.scraper_id}")
            if os.path.exists(profile_dir):
                try:
                    remover_diretorio(profile_dir)
                except:
                    pass
                    
        except Exception as e:
            logger.error(f"[Scraper {self.scraper_id}] Erro na limpeza: {e}")
    
    
    def executar_scraper(self, ano: int, mes_inicio: str, mes_fim: str) -> List[Dict[str, Any]]:
        """
        Executa o scraper para coletar dados do Portal da Transparência.
        
        Args:
            ano: Ano para o qual os dados serão coletados.
            mes_inicio: Mês inicial para a coleta de dados (ex: "JANEIRO").
            mes_fim: Mês final para a coleta de dados (ex: "DEZEMBRO").
            
        Returns:
            Lista de dicionários contendo os dados coletados.
            
        Raises:
            HTTPException: Em caso de erro durante a execução.
        """
        logger.info(f"[Scraper {self.scraper_id}] Iniciando para ano={ano}, mes_inicio={mes_inicio}, mes_fim={mes_fim}, thread={self.thread_id}")
        
        # Adicionar delay aleatório para evitar condições de corrida
        delay = random.uniform(0.5, 2.0)
        logger.debug(f"[Scraper {self.scraper_id}] Aguardando {delay:.2f}s antes de iniciar...")
        time.sleep(delay)
        
        try:
            with TimerContext("iniciar_navegador") as timer_navegador:
                self._iniciar_navegador()
            
            with TimerContext("acessar_url") as timer_url:
                # Acessa a URL de consulta
                url = "https://www.transparencia.pr.gov.br/pte/assunto/4/22?origem=3"
                logger.info(f"[Scraper {self.scraper_id}] Acessando URL: {url}")
                self.driver.get(url)
                
                # Aguardar página carregar completamente
                WebDriverWait(self.driver, 20).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                time.sleep(3)  # Aguarda adicional para garantir
            
            with TimerContext("preencher_formulario") as timer_formulario:
                # Preenche o formulário com os parâmetros
                self._preencher_formulario(ano, mes_inicio, mes_fim)
                # Aguarda processamento do formulário
                time.sleep(2)
            
            with TimerContext("clicar_botao_pesquisa") as timer_pesquisa:
                # Clica no botão de pesquisa
                self._clicar_botao_pesquisa()
                # Aguarda resultados carregarem
                time.sleep(3)
            
            with TimerContext("baixar_processar_planilha") as timer_planilha:
                # Baixa e processa a planilha
                logger.info(f"[Scraper {self.scraper_id}] Iniciando download e processamento da planilha...")
                
                # Passar o scraper_id para o processamento da planilha
                dados = baixar_e_processar_planilha(self.driver, self.download_dir, scraper_id=self.scraper_id)
                
                logger.info(f"[Scraper {self.scraper_id}] Processamento concluído, {len(dados) if dados else 0} registros obtidos")
            
            # Log detalhado dos tempos
            logger.info(f"[Scraper {self.scraper_id}] Tempos de execução - Navegador: {timer_navegador.get_duration():.2f}s, "
                       f"URL: {timer_url.get_duration():.2f}s, "
                       f"Formulário: {timer_formulario.get_duration():.2f}s, "
                       f"Pesquisa: {timer_pesquisa.get_duration():.2f}s, "
                       f"Planilha: {timer_planilha.get_duration():.2f}s")
            
            return dados
            
        except Exception as e:
            logger.error(f"[Scraper {self.scraper_id}] Erro: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
            
        finally:
            self.cleanup()


