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
import logging
import time
from typing import List, Dict, Any, Tuple, Callable, Optional

# Configuração de logging
logger = logging.getLogger(__name__)


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
    
    def _iniciar_navegador(self) -> None:
        """Inicia o navegador Chrome com as opções configuradas."""
        logger.info("Criando diretório temporário para downloads...")
        self.download_dir = criar_diretorio_temporario()
        
        logger.info("Iniciando o navegador Chrome...")
        self.driver = iniciar_navegador(headless=self.headless, download_dir=self.download_dir)
        logger.info("Navegador iniciado com sucesso")
    
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
        orgao_desejado = "45 - SECRETARIA DE ESTADO DA CIÊNCIA, TECNOLO"
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
        logger.info(f"Iniciando scraper para ano={ano}, mes_inicio={mes_inicio}, mes_fim={mes_fim}")
        
        try:
            self._iniciar_navegador()
            
            # Acessa a URL de consulta
            url = "https://www.transparencia.pr.gov.br/pte/assunto/4/22?origem=3"
            logger.info(f"Acessando URL: {url}")
            self.driver.get(url)
            time.sleep(5)  # Aguarda carregar
            
            # Preenche o formulário com os parâmetros
            self._preencher_formulario(ano, mes_inicio, mes_fim)
            
            # Clica no botão de pesquisa
            self._clicar_botao_pesquisa()
            
            # Baixa e processa a planilha
            logger.info("Iniciando download e processamento da planilha...")
            dados = baixar_e_processar_planilha(self.driver, self.download_dir)
            logger.info(f"Processamento concluído, {len(dados) if dados else 0} registros obtidos")
            
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao executar o scraper: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
            
        finally:
            if self.driver:
                logger.info("Fechando o navegador...")
                self.driver.quit()
                
            if self.download_dir:
                logger.info("Limpando diretório de download...")
                remover_diretorio(self.download_dir)


