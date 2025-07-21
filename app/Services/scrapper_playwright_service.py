from playwright.async_api import async_playwright, Browser, Page, BrowserContext
from fastapi import HTTPException
from app.utils.planilha_playwright import baixar_e_processar_planilha_playwright
from app.utils.file_utils import criar_diretorio_temporario, remover_diretorio
from app.utils.performance_tracker import TimerContext
import logging
import asyncio
import aiofiles
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

# Configuração de logging
logger = logging.getLogger(__name__)


class TransparenciaPlaywrightScraper:
    """Classe assíncrona para extrair dados do Portal da Transparência do Paraná usando Playwright."""
    
    def __init__(self, headless: bool = True):
        """
        Inicializa o scraper.
        
        Args:
            headless: Se True, executa o navegador em modo headless.
        """
        self.headless = headless
        self.browser = None
        self.context = None
        self.page = None
        self.download_dir = None
        self.playwright = None
    
    async def _iniciar_navegador(self) -> None:
        """Inicia o navegador com as opções configuradas."""
        logger.info("Criando diretório temporário para downloads...")
        self.download_dir = criar_diretorio_temporario()
        
        logger.info("Iniciando o navegador com Playwright...")
        self.playwright = await async_playwright().start()
        
        # Configurações do navegador
        self.browser = await self.playwright.chromium.launch(
            headless=self.headless,
            args=[
                '--no-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-web-security',
                '--allow-running-insecure-content'
            ]
        )
        
        # Criação do contexto com configurações de download
        self.context = await self.browser.new_context(
            accept_downloads=True,
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'        )
        
        # Configurar interceptação de downloads
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => false,
            });
        """)
        
        self.page = await self.context.new_page()
        
        # Configurar timeout padrão
        self.page.set_default_timeout(30000)  # 30 segundos
        
        logger.info("Navegador iniciado com sucesso")
    
    async def _preencher_formulario(self, ano: int, mes_inicio: str, mes_fim: str) -> None:
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
        await self.page.evaluate(f"""
            document.getElementById('formPesquisaDespesa:filtroAno_input').value = '{ano}';
            PrimeFaces.ab({{s:'formPesquisaDespesa:filtroAno',e:'change'}});
        """)

        # ----- CAMPO MÊS INICIAL -----
        logger.info(f"Configurando mês inicial: {mes_inicio}")

        await self.page.evaluate(f"""
            document.getElementById('formPesquisaDespesa:filtroMesInicio_input').value = '{mes_inicio}';
            PrimeFaces.ab({{s:'formPesquisaDespesa:filtroMesInicio',e:'change'}});
        """)

        # ----- CAMPO MÊS FINAL -----
        logger.info(f"Configurando mês final: {mes_fim}")
        await self.page.evaluate(f"""
            document.getElementById('formPesquisaDespesa:filtroMesTermino_input').value = '{mes_fim}';
            PrimeFaces.ab({{s:'formPesquisaDespesa:filtroMesTermino',e:'change'}});
        """)
                
        logger.info("Formulário preenchido com sucesso")
        # ----- CAMPO ÓRGÃO -----
        logger.info("Configurando campo de órgão...")
        orgao_desejado = "45 - SECRETARIA DE ESTADO DA CIÊNCIA, TECNOLO"
        orgao_value = "UniqueKey[codigo=45, exercicio=2023]"
        await self.page.evaluate(f"""
            var orgaoInput = document.getElementById('formPesquisaDespesa:detalheFiltroOrgao_input');
            orgaoInput.value = '{orgao_desejado}';
            orgaoInput.dispatchEvent(new Event('change', {{ bubbles: true }}));
            orgaoInput.dispatchEvent(new Event('input', {{ bubbles: true }}));
            var orgaoHidden = document.getElementById('formPesquisaDespesa:detalheFiltroOrgao');
            orgaoHidden.value = '{orgao_value}';
            orgaoHidden.dispatchEvent(new Event('change', {{ bubbles: true }}));
        """)
        
        logger.info(f"Órgão selecionado: {orgao_desejado}")
        
        # ----- CHECKBOXES -----
        await self._marcar_checkbox('formPesquisaDespesa:detalheFiltroUnidadeOrcamentaria', "unidades orçamentárias")
        await self._marcar_checkbox('formPesquisaDespesa:detalheFiltroFuncao', "funções")
        await self._marcar_checkbox('formPesquisaDespesa:detalheFiltroOrigemRecursos', "origens de recursos")
        await self._marcar_checkbox('formPesquisaDespesa:detalheFiltroGrupoDespesaNatureza', "grupos de natureza de despesa")
        

    async def _marcar_checkbox(self, id_base: str, descricao: str) -> None:
        """
        Marca um checkbox específico no formulário.
        
        Args:
            id_base: ID base do checkbox (sem sufixos como '_input').
            descricao: Descrição do checkbox para logs.
        """
        logger.info(f"Marcando checkbox de {descricao}...")
        
        await self.page.evaluate(f"""
            var inputElement = document.getElementById('{id_base}_input');
            if (inputElement && !inputElement.checked) {{
                inputElement.checked = true;
                
                var boxElements = document.getElementsByClassName('{id_base}');
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
    
    async def _clicar_botao_pesquisa(self) -> None:
      """
      Clica no botão de pesquisa e aguarda o carregamento dos resultados.
      Lida com possíveis overlays que possam estar bloqueando o botão.
      """
      logger.info("Preparando para clicar no botão de pesquisa...")
      
      # Tentativa 1: Remover qualquer overlay que possa estar bloqueando
      try:
          logger.info("Removendo overlays e modais...")
          await self.page.evaluate("""
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
      
      # Tentativa 2: Usar JavaScript para clicar no botão diretamente (mais confiável)
      try:
          logger.info("Tentando clicar no botão via JavaScript PrimeFaces...")
          resultado = await self.page.evaluate("""
              () => {
                  try {
                      // Verifica se PrimeFaces está disponível
                      if (typeof PrimeFaces === 'undefined') {
                          return { sucesso: false, erro: 'PrimeFaces não está disponível' };
                      }
                      
                      // Abordagem 1: Usar o evento PrimeFaces diretamente
                      PrimeFaces.ab({
                          s: 'formPesquisaDespesa:btnPesquisar',
                          p: 'formPesquisaDespesa',
                          u: 'formPesquisaDespesa',
                          onco: function(xhr, status, args) { 
                              if (typeof iniciarPopover === 'function') {
                                  iniciarPopover(); 
                              }
                          }
                      });
                      
                      return { sucesso: true, metodo: 'PrimeFaces.ab()' };
                      
                  } catch (erro) {
                      return { sucesso: false, erro: erro.toString() };
                  }
              }
          """)
          
          if resultado['sucesso']:
              logger.info(f"Botão clicado via JavaScript: {resultado['metodo']}")
          else:
              raise Exception(resultado['erro'])
              
      except Exception as e:
          logger.warning(f"Falha ao clicar via PrimeFaces.ab(): {e}")                  
      
      # Aguarda carregamento dos resultados
      logger.info("Aguardando carregamento dos resultados...")
      
      # Aguarda até que a página não esteja mais carregando
      try:
          await self.page.wait_for_load_state('networkidle', timeout=60000)
          logger.info("Página carregada completamente após pesquisa")
      except Exception as e:
          logger.warning(f"Timeout aguardando carregamento após pesquisa: {e}")
      
      # Verificar se a pesquisa foi bem-sucedida
      try:
          logger.info("Verificando se os resultados foram carregados...")
          # Essa verificação é a partir da url que tem que conter: https://www.transparencia.pr.gov.br/pte/despesas/consultalivre/listar?
          url = self.page.url
          if "https://www.transparencia.pr.gov.br/pte/despesas/consultalivre/listar?" not in url:
              screenshot_path = os.path.join('./', "sem_resultados_screenshot.png")
              await self.page.screenshot(path=screenshot_path, full_page=True)
              logger.info(f"Screenshot salvo para debug: {screenshot_path}")
              raise Exception("A URL não corresponde ao padrão esperado após a pesquisa")                  
                  
      except Exception as e:
          logger.warning(f"Não foi possível verificar os resultados: {e}")
    
    async def obter_dados_transparencia(self, ano: int, mes_inicio: str = "01", mes_fim: str = "12") -> Optional[List[Dict[str, Any]]]:
        """
        Método principal para obter dados do Portal da Transparência.
        
        Args:
            ano: Ano para o qual os dados serão coletados.
            mes_inicio: Mês inicial (padrão: "01").
            mes_fim: Mês final (padrão: "12").
            
        Returns:
            Lista de dicionários com os dados coletados ou None em caso de erro.
        """
        logger.info(f"Iniciando coleta de dados para o ano {ano} (meses {mes_inicio} a {mes_fim})")
        
        try:
            with TimerContext("iniciar_navegador_playwright") as timer_navegador:
                await self._iniciar_navegador()
            
            with TimerContext("navegar_para_url") as timer_url:
                # Navega para a página
                logger.info("Navegando para o Portal da Transparência...")
                url = "https://www.transparencia.pr.gov.br/pte/assunto/4/22?origem=3"
                await self.page.goto(url, wait_until='domcontentloaded')
                logger.info("Página carregada")
                
                
            with TimerContext("preencher_formulario_playwright") as timer_formulario:
                # Preenche o formulário com os parâmetros
                await self._preencher_formulario(ano, mes_inicio, mes_fim)
            
            with TimerContext("clicar_botao_pesquisa_playwright") as timer_pesquisa:
                # Clica no botão de pesquisa
                await self._clicar_botao_pesquisa()
            
            with TimerContext("baixar_processar_planilha_playwright") as timer_planilha:            
                logger.info("Iniciando download e processamento da planilha...")
                dados = await baixar_e_processar_planilha_playwright(self.page, self.download_dir)
                logger.info(f"Processamento concluído, {len(dados) if dados else 0} registros obtidos")
            
            # Log detalhado dos tempos
            logger.info(f"Tempos de execução Playwright - Navegador: {timer_navegador.get_duration():.2f}s, "
                       f"URL: {timer_url.get_duration():.2f}s, "
                       f"Formulário: {timer_formulario.get_duration():.2f}s, "
                       f"Pesquisa: {timer_pesquisa.get_duration():.2f}s, "
                       f"Planilha: {timer_planilha.get_duration():.2f}s")
            
            return dados
            
        except Exception as e:
            logger.error(f"Erro ao executar o scraper Playwright: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=str(e))
            
        finally:
            await self._fechar_navegador()
    
    async def _fechar_navegador(self) -> None:
        """Fecha o navegador e limpa recursos."""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            
            if self.download_dir:
                logger.info("Limpando diretório de download...")
                remover_diretorio(self.download_dir)
                
        except Exception as e:
            logger.error(f"Erro ao fechar navegador: {e}")


# Função utilitária para execução assíncrona de múltiplos anos
async def executar_consulta_multiplos_anos_playwright(anos: List[int], mes_inicio: str = "01", mes_fim: str = "12") -> Dict[str, Any]:
    """
    Executa consultas para múltiplos anos de forma assíncrona.
    
    Args:
        anos: Lista de anos para consultar.
        mes_inicio: Mês inicial.
        mes_fim: Mês final.
        
    Returns:
        Dicionário com os resultados consolidados.
    """
    resultados = []
    erros = []
    
    # Função para processar um ano
    async def processar_ano(ano: int) -> Dict[str, Any]:
        try:
            scraper = TransparenciaPlaywrightScraper(headless=False)
            dados = await scraper.obter_dados_transparencia(ano, mes_inicio, mes_fim)
            return {"ano": ano, "dados": dados, "sucesso": True}
        except Exception as e:
            logger.error(f"Erro ao processar ano {ano}: {e}")
            return {"ano": ano, "erro": str(e), "sucesso": False}
    
    # Executa consultas em paralelo (limitando a concorrência)
    semaforo = asyncio.Semaphore(3)  # Máximo 3 consultas simultâneas
    
    async def processar_com_semaforo(ano: int):
        async with semaforo:
            return await processar_ano(ano)
    
    # Executa todas as consultas
    tasks = [processar_com_semaforo(ano) for ano in anos]
    resultados_brutos = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Processa os resultados
    for resultado in resultados_brutos:
        if isinstance(resultado, Exception):
            erros.append(str(resultado))
        elif resultado["sucesso"]:
            if resultado["dados"]:
                resultados.extend(resultado["dados"])
        else:
            erros.append(f"Ano {resultado['ano']}: {resultado['erro']}")
    
    return {
        "dados": resultados,
        "total_registros": len(resultados),
        "anos_processados": len([r for r in resultados_brutos if not isinstance(r, Exception) and r["sucesso"]]),
        "erros": erros
    }
