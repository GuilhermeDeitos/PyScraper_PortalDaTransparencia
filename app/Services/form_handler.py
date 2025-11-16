import logging
from selenium import webdriver
from app.utils.browser_utils import executar_javascript_seguro

logger = logging.getLogger(__name__)

class FormHandler:
    """Gerencia interação com formulários do Portal da Transparência."""
    
    ORGAO_CODIGO = "45"
    ORGAO_VALUE = "UniqueKey[codigo=45, exercicio=2023]"
    
    def __init__(self, driver: webdriver.Chrome, scraper_id: str):
        self.driver = driver
        self.scraper_id = scraper_id
    
    def preencher_pesquisa(self, ano: int, mes_inicio: str, mes_fim: str):
        """Preenche formulário de pesquisa."""
        self._preencher_ano(ano)
        self._preencher_mes_inicio(mes_inicio)
        self._preencher_mes_fim(mes_fim)
        self._selecionar_orgao()
        self._marcar_detalhamentos()
    
    def _preencher_ano(self, ano: int):
        logger.debug(f"[{self.scraper_id}] Preenchendo ano: {ano}")
        executar_javascript_seguro(
            self.driver,
            f"document.getElementById('formPesquisaDespesa:filtroAno_input').value = '{ano}';"
            f"PrimeFaces.ab({{s:'formPesquisaDespesa:filtroAno',e:'change'}});"
        )
    
    def _preencher_mes_inicio(self, mes: str):
        logger.debug(f"[{self.scraper_id}] Preenchendo mês início: {mes}")
        executar_javascript_seguro(
            self.driver,
            f"document.getElementById('formPesquisaDespesa:filtroMesInicio_input').value = '{mes}';"
            f"PrimeFaces.ab({{s:'formPesquisaDespesa:filtroMesInicio',e:'change'}});"
        )
    
    def _preencher_mes_fim(self, mes: str):
        logger.debug(f"[{self.scraper_id}] Preenchendo mês fim: {mes}")
        executar_javascript_seguro(
            self.driver,
            f"document.getElementById('formPesquisaDespesa:filtroMesTermino_input').value = '{mes}';"
            f"PrimeFaces.ab({{s:'formPesquisaDespesa:filtroMesTermino',e:'change'}});"
        )
    
    def _selecionar_orgao(self):
        logger.debug(f"[{self.scraper_id}] Selecionando órgão: {self.ORGAO_CODIGO}")
        executar_javascript_seguro(
            self.driver,
            f"var select = document.getElementById('formPesquisaDespesa:filtroOrgao_input');"
            f"select.value = '{self.ORGAO_VALUE}';"
            f"PrimeFaces.ab({{s:'formPesquisaDespesa:filtroOrgao',e:'change'}});"
        )
    
    def _marcar_detalhamentos(self):
        checkboxes = [
            ('formPesquisaDespesa:detalheFiltroUnidadeOrcamentaria', 'unidades'),
            ('formPesquisaDespesa:detalheFiltroFuncao', 'funções'),
            ('formPesquisaDespesa:detalheFiltroOrigemRecursos', 'origens'),
            ('formPesquisaDespesa:detalhFiltroGrupoDespesaNatureza', 'grupos'),
        ]
        
        for id_checkbox, descricao in checkboxes:
            self._marcar_checkbox(id_checkbox, descricao)
    
    def _marcar_checkbox(self, id_base: str, descricao: str):
        logger.debug(f"[{self.scraper_id}] Marcando checkbox: {descricao}")
        executar_javascript_seguro(
            self.driver,
            f"""
            var input = document.getElementById('{id_base}_input');
            input.checked = true;
            input.dispatchEvent(new Event('change', {{ bubbles: true }}));
            PrimeFaces.ab({{s:'{id_base}', e:'change'}});
            """
        )