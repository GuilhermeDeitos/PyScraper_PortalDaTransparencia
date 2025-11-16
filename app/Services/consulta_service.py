import logging
import time
import random
import uuid
from typing import List, Dict, Any, Optional
from fastapi import BackgroundTasks, HTTPException

from app.Models.Schema import ConsultaParams
from app.Repositories.consulta_repo import ConsultaRepository
from app.Services.scrapper_service import TransparenciaScraper
from app.Services.concurrency_manager import ConcurrencyManager, ConcurrencyConfig
from app.Services.query_optimizer import QueryOptimizer
from app.Services.data_validator import DataValidator
from app.utils.validators import validar_parametros
from app.utils.date_utils import dict_mes_numero

logger = logging.getLogger(__name__)

class ConsultaService:
    """Serviço de consulta ao Portal da Transparência."""
    
    def __init__(
        self, 
        concurrency_config: Optional[ConcurrencyConfig] = None
    ):
        self.consulta_repo = ConsultaRepository()
        self.concurrency = ConcurrencyManager(concurrency_config)
        self.optimizer = QueryOptimizer()
        self.validator = DataValidator()
        self.consultas_canceladas = set()
    
    async def processar_consulta(
        self, 
        params: ConsultaParams, 
        background_tasks: BackgroundTasks
    ):
        """Processa uma consulta de dados do Portal da Transparência."""
        mes_inicio, ano_inicio, mes_fim, ano_fim = validar_parametros(
            params.data_inicio, params.data_fim
        )
        
        estrategias = self.optimizer.definir_estrategia(
            ano_inicio, mes_inicio, ano_fim, mes_fim
        )
        
        total_anos = len(estrategias)
        anos_locais, anos_scraper = self.optimizer.calcular_estatisticas(estrategias)
        
        logger.info(
            f"Consulta: {anos_locais}/{total_anos} anos via local, "
            f"{anos_scraper}/{total_anos} anos via scraper"
        )
        
        if self._deve_processar_sincronamente(total_anos, estrategias):
            return await self._processar_sincronamente(
                ano_inicio, estrategias[ano_inicio]
            )
        
        return await self._processar_assincronamente(
            ano_inicio, mes_inicio, ano_fim, mes_fim, 
            estrategias, background_tasks
        )
    
    def _deve_processar_sincronamente(
        self, 
        total_anos: int, 
        estrategias: Dict
    ) -> bool:
        """Decide se deve processar sincronamente."""
        slots_disponiveis = self.concurrency.get_available_slots()
        return total_anos == 1 and slots_disponiveis > 0
    
    async def _processar_sincronamente(
        self, 
        ano: int, 
        estrategia
    ) -> Dict[str, Any]:
        """Processa um único ano de forma síncrona."""
        inicio = time.time()
        
        if estrategia.usar_dados_locais:
            resultado = self.optimizer.consulta_local.obter_dados_ano(ano)
        else:
            with self.concurrency.semaphore:
                resultado = self._executar_scraper_com_retry(
                    ano, 
                    estrategia.periodo.mes_inicio, 
                    estrategia.periodo.mes_fim
                )
        
        tempo = time.time() - inicio
        total_registros = len(resultado) if resultado else 0
        
        return {
            "dados": resultado,
            "dados_por_ano": {
                str(ano): {
                    "dados": resultado,
                    "total_registros": total_registros,
                    "mes_inicio": estrategia.periodo.mes_inicio,
                    "mes_fim": estrategia.periodo.mes_fim,
                    "processado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "fonte_dados": estrategia.fonte,
                    "tempo_processamento": round(tempo, 2)
                }
            },
            "total_registros": total_registros,
            "anos_processados": [ano],
            "processamento": "sincrono",
            "fonte_dados": estrategia.fonte
        }
    
    async def _processar_assincronamente(
        self, 
        ano_inicio: int, 
        mes_inicio: int, 
        ano_fim: int, 
        mes_fim: int,
        estrategias: Dict,
        background_tasks: BackgroundTasks
    ) -> Dict[str, Any]:
        """Inicia processamento assíncrono."""
        id_consulta = str(uuid.uuid4())
        
        self.consulta_repo.iniciar_consulta(
            id_consulta,
            anos_range=(ano_inicio, ano_fim),
            mes_inicio=mes_inicio,
            mes_fim=mes_fim
        )
        
        for ano, estrategia in estrategias.items():
            self.consulta_repo.adicionar_metadados_ano(
                id_consulta, ano,
                {
                    "estrategia_processamento": estrategia.fonte,
                    "mes_inicio": estrategia.periodo.mes_inicio,
                    "mes_fim": estrategia.periodo.mes_fim
                }
            )
        
        background_tasks.add_task(
            self._processar_em_background,
            id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim
        )
        
        anos_locais, anos_scraper = self.optimizer.calcular_estatisticas(estrategias)
        
        return {
            "status": "processando",
            "mensagem": f"Consulta para {mes_inicio:02d}/{ano_inicio} a {mes_fim:02d}/{ano_fim} iniciada",
            "id_consulta": id_consulta,
            "consultar_status": f"/status-consulta/{id_consulta}",
            "total_anos": len(estrategias),
            "anos_otimizados": anos_locais,
            "anos_scraper": anos_scraper,
            "recursos": self.concurrency.get_status()
        }
    
    def _processar_em_background(
        self, 
        id_consulta: str, 
        ano_inicio: int, 
        mes_inicio: int, 
        ano_fim: int, 
        mes_fim: int
    ):
        """Submete tarefa ao pool de threads."""
        future = self.concurrency.submit_task(
            self._executar_consulta_por_anos,
            id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim
        )
        
        def log_completion(f):
            try:
                f.result()
                logger.info(f"Consulta {id_consulta} concluída")
            except Exception as e:
                logger.error(f"Consulta {id_consulta} falhou: {e}")
        
        future.add_done_callback(log_completion)
    
    def _executar_consulta_por_anos(
        self, 
        id_consulta: str, 
        ano_inicio: int, 
        mes_inicio: int, 
        ano_fim: int, 
        mes_fim: int
    ):
        """Executa consulta processando cada ano."""
        inicio_total = time.time()
        
        try:
            if id_consulta in self.consultas_canceladas:
                self._finalizar_como_cancelada(id_consulta)
                return
            
            estrategias = self.optimizer.definir_estrategia(
                ano_inicio, mes_inicio, ano_fim, mes_fim
            )
            
            for idx, (ano, estrategia) in enumerate(estrategias.items(), 1):
                if self._verificar_cancelamento(id_consulta, idx, len(estrategias)):
                    break
                
                self._processar_ano(id_consulta, ano, estrategia, idx, len(estrategias))
            
            self._finalizar_consulta(id_consulta, inicio_total)
            
        except Exception as e:
            logger.error(f"Erro na consulta {id_consulta}: {e}", exc_info=True)
            self.consulta_repo.registrar_erro_consulta(id_consulta, str(e))
    
    def _processar_ano(
        self, 
        id_consulta: str, 
        ano: int, 
        estrategia, 
        idx: int, 
        total: int
    ):
        """Processa um ano específico."""
        progresso = f"{idx}/{total}"
        periodo = estrategia.periodo
        
        self.consulta_repo.atualizar_status_processando(
            id_consulta,
            f"Processando ano {ano} ({periodo.mes_inicio:02d}-{periodo.mes_fim:02d}) "
            f"via {estrategia.fonte} ({progresso})"
        )
        
        try:
            if estrategia.usar_dados_locais:
                resultado = self._processar_ano_local(ano, periodo)
            else:
                resultado = self._processar_ano_scraper(id_consulta, ano, periodo)
            
            if resultado:
                self.consulta_repo.adicionar_resultados_ano(
                    id_consulta, ano, resultado, 
                    periodo.mes_inicio, periodo.mes_fim
                )
            
        except Exception as e:
            logger.error(f"Erro ao processar ano {ano}: {e}")
            self.consulta_repo.registrar_erro_ano(id_consulta, ano, str(e))
    
    def _processar_ano_local(self, ano: int, periodo) -> List[Dict[str, Any]]:
        """Processa ano usando dados locais."""
        resultado = self.optimizer.consulta_local.obter_dados_ano(ano)
        logger.info(f"Ano {ano} via local: {len(resultado)} registros")
        return resultado
    
    def _processar_ano_scraper(
        self, 
        id_consulta: str, 
        ano: int, 
        periodo
    ) -> List[Dict[str, Any]]:
        """Processa ano usando scraper."""
        ano_lock = self.concurrency.get_lock_for_ano(ano)
        
        if not ano_lock.acquire(blocking=False):
            raise Exception(f"Ano {ano} já em processamento")
        
        try:
            with self.concurrency.semaphore:
                return self._executar_scraper_com_retry(
                    ano, periodo.mes_inicio, periodo.mes_fim, id_consulta
                )
        finally:
            ano_lock.release()
    
    def _executar_scraper_com_retry(
        self, 
        ano: int, 
        mes_inicio: int, 
        mes_fim: int,
        id_consulta: Optional[str] = None,
        max_retries: int = 2
    ) -> List[Dict[str, Any]]:
        """Executa scraper com retry e validação."""
        for tentativa in range(max_retries + 1):
            if id_consulta and id_consulta in self.consultas_canceladas:
                raise Exception("Consulta cancelada")
            
            try:
                scraper = TransparenciaScraper(headless=True)
                resultado = scraper.executar_scraper(
                    ano, 
                    dict_mes_numero[mes_inicio], 
                    dict_mes_numero[mes_fim]
                )
                
                resultado_validado = self.validator.validar_dados_ano(resultado, ano)
                
                if not self.validator.validar_taxa_sucesso(resultado_validado, resultado):
                    if tentativa < max_retries:
                        raise Exception("Taxa de validade baixa")
                
                return resultado_validado
                
            except Exception as e:
                logger.warning(f"Tentativa {tentativa + 1} falhou: {e}")
                
                if tentativa < max_retries:
                    time.sleep((tentativa + 1) * 3 + random.uniform(0, 2))
                else:
                    raise
    
    def _verificar_cancelamento(
        self, 
        id_consulta: str, 
        idx: int, 
        total: int
    ) -> bool:
        """Verifica se consulta foi cancelada."""
        if id_consulta in self.consultas_canceladas:
            self.consulta_repo.atualizar_status_processando(
                id_consulta,
                f"Cancelado após processar {idx-1}/{total} anos"
            )
            self._finalizar_como_cancelada(id_consulta)
            return True
        return False
    
    def _finalizar_como_cancelada(self, id_consulta: str):
        """Finaliza consulta como cancelada."""
        self.consulta_repo.finalizar_consulta(id_consulta, status="cancelada")
        self.consultas_canceladas.discard(id_consulta)
    
    def _finalizar_consulta(self, id_consulta: str, inicio_total: float):
        """Finaliza consulta com sucesso."""
        tempo_total = time.time() - inicio_total
        
        if id_consulta in self.consultas_canceladas:
            self._finalizar_como_cancelada(id_consulta)
        else:
            self.consulta_repo.finalizar_consulta(id_consulta)
            logger.info(f"Consulta {id_consulta} concluída em {tempo_total:.2f}s")
    
    def cancelar_consulta(self, id_consulta: str):
        """Marca consulta para cancelamento."""
        logger.info(f"Cancelando consulta {id_consulta}")
        self.consultas_canceladas.add(id_consulta)
        self.consulta_repo.atualizar_status_processando(
            id_consulta,
            "Cancelamento solicitado"
        )
        return {"status": "cancelamento_solicitado"}
    
    def obter_status_consulta(self, id_consulta: str):
        """Obtém status de uma consulta."""
        return self.consulta_repo.obter_consulta(id_consulta)
    
    def obter_dados_ano_especifico(self, id_consulta: str, ano: int):
        """Obtém dados de um ano específico."""
        consulta = self.consulta_repo.obter_consulta(id_consulta)
        
        if "error" in consulta:
            return consulta
        
        dados_por_ano = consulta.get("dados_por_ano", {})
        if str(ano) in dados_por_ano:
            return {
                "ano": ano,
                **dados_por_ano[str(ano)]
            }
        
        return {"error": f"Dados do ano {ano} não encontrados"}
    
    def get_system_status(self):
        """Retorna status do sistema."""
        return self.concurrency.get_status()


# Função auxiliar para ser importada em routes
def get_system_status() -> Dict[str, Any]:
    """
    Função auxiliar para obter status do sistema sem instanciar ConsultaService.
    Retorna informações básicas sobre o sistema.
    """
    import threading
    import psutil
    
    try:
        process = psutil.Process()
        cpu_percent = process.cpu_percent(interval=0.1)
        memory_info = process.memory_info()
        memory_mb = memory_info.rss / (1024 * 1024)
    except Exception:
        cpu_percent = 0
        memory_mb = 0
    
    return {
        "status": "online",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "threads_ativos": threading.active_count(),
        "recursos": {
            "cpu_percent": round(cpu_percent, 2),
            "memoria_mb": round(memory_mb, 2)
        },
        "organizacao_dados": "por_ano",
        "versao": "2.0.0"
    }