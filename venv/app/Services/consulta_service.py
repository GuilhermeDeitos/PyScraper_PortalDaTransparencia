from fastapi import BackgroundTasks
import threading
import uuid
import logging
from app.Models.Schema import ConsultaParams
from app.Repositories.consulta_repo import ConsultaRepository
from app.Services.scrapper_service import TransparenciaScraper
from app.utils.validators import validar_parametros
from app.utils.date_utils import dict_mes_numero

logger = logging.getLogger(__name__)

class ConsultaService:
    def __init__(self):
        self.consulta_repo = ConsultaRepository()
        self.scraper_service = TransparenciaScraper(headless=True)
    
    async def processar_consulta(self, params: ConsultaParams, background_tasks: BackgroundTasks):
        """Processa uma consulta de dados do Portal da Transparência"""
        mes_inicio, ano_inicio, mes_fim, ano_fim = validar_parametros(
            params.data_inicio, params.data_fim
        )
        
        if ano_inicio != ano_fim:
            # Processamento assíncrono para múltiplos anos
            id_consulta = str(uuid.uuid4())
            
            # Inicializa o registro da consulta
            self.consulta_repo.iniciar_consulta(
                id_consulta, 
                anos_range=(ano_inicio, ano_fim)
            )
            
            # Inicia processamento em background
            background_tasks.add_task(
                self._processar_em_background,
                id_consulta,
                ano_inicio,
                mes_inicio,
                ano_fim,
                mes_fim
            )
            
            return {
                "status": "processando",
                "mensagem": f"Consulta para os anos {ano_inicio} a {ano_fim} iniciada em background",
                "id_consulta": id_consulta,
                "consultar_status": f"/status-consulta/{id_consulta}"
            }
        else:
            # Processamento síncrono para um único ano
            resultado = self.scraper_service.executar_scraper(
                ano_inicio, 
                dict_mes_numero[mes_inicio], 
                dict_mes_numero[mes_fim]
            )
            
            return {
                "dados": resultado,
                "total_registros": len(resultado)
            }
    
    def _processar_em_background(self, id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim):
        """Inicia thread para processamento em background"""
        thread = threading.Thread(
            target=self._executar_consulta_sequencial,
            args=(id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim)
        )
        thread.daemon = True
        thread.start()
    
    def _executar_consulta_sequencial(self, id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim):
        """Executa consulta sequencial para múltiplos anos"""
        try:
            for ano in range(ano_inicio, ano_fim + 1):
                mes_inicial_ano = mes_inicio if ano == ano_inicio else 1
                mes_final_ano = mes_fim if ano == ano_fim else 12
                
                # Atualiza status
                self.consulta_repo.atualizar_status_processando(
                    id_consulta, 
                    f"Processando ano {ano} - {dict_mes_numero[mes_inicial_ano]} a {dict_mes_numero[mes_final_ano]}"
                )
                
                try:
                    # Executa o scraper para o ano
                    resultado_ano = self.scraper_service.executar_scraper(
                        ano, 
                        dict_mes_numero[mes_inicial_ano], 
                        dict_mes_numero[mes_final_ano]
                    )
                    
                    # Registra resultados
                    self.consulta_repo.adicionar_resultados_ano(
                        id_consulta, ano, resultado_ano
                    )
                    
                except Exception as e:
                    logger.error(f"Erro ao processar ano {ano}: {e}")
                    self.consulta_repo.registrar_erro_ano(id_consulta, ano, str(e))
            
            # Finaliza a consulta como concluída
            self.consulta_repo.finalizar_consulta(id_consulta)
            
        except Exception as e:
            logger.error(f"Erro na execução da consulta {id_consulta}: {e}", exc_info=True)
            self.consulta_repo.registrar_erro_consulta(id_consulta, str(e))
    
    def obter_status_consulta(self, id_consulta):
        """Obtém o status atual de uma consulta"""
        return self.consulta_repo.obter_consulta(id_consulta)