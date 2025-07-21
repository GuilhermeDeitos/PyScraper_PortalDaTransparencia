import asyncio
import uuid
import logging
from typing import Dict, Any, List, Optional
from fastapi import BackgroundTasks
from app.Models.Schema import ConsultaParams
from app.Repositories.consulta_playwright_repo import ConsultaPlaywrightRepository
from app.Services.scrapper_playwright_service import TransparenciaPlaywrightScraper, executar_consulta_multiplos_anos_playwright
from app.utils.validators import validar_parametros
from app.utils.date_utils import obter_range_anos, formatar_mes, dict_mes_numero
from app.utils.performance_tracker import TimerContext, performance_tracker
from datetime import datetime

logger = logging.getLogger(__name__)


class ConsultaPlaywrightService:
    """Serviço para gerenciar consultas usando Playwright de forma assíncrona"""
    
    def __init__(self):
        self.repository = ConsultaPlaywrightRepository()
    
    async def processar_consulta(self, params: ConsultaParams, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        """
        Processa uma consulta de dados do Portal da Transparência usando Playwright.
        
        Args:
            params: Parâmetros da consulta.
            background_tasks: Tarefas em background do FastAPI.
            
        Returns:
            Resultado da consulta ou ID para acompanhamento assíncrono.
        """
        try:
            # Valida os parâmetros
            mes_inicio, ano_inicio, mes_fim, ano_fim = validar_parametros(params.data_inicio, params.data_fim)
            
            # Obtém o range de anos
            range_anos = obter_range_anos(params.data_inicio, params.data_fim)
            anos = list(range(range_anos[0], range_anos[1] + 1))

            logger.info(f"Iniciando consulta Playwright para anos {anos} (meses {mes_inicio} a {mes_fim})")
            
            # Determina se deve ser processamento assíncrono
            # Para mais de 1 ano, sempre assíncrono
            if len(anos) > 1:
                return await self._processar_consulta_assincrona(anos, dict_mes_numero[mes_inicio], dict_mes_numero[mes_fim], background_tasks)
            else:
                # Para um ano, pode ser síncrono
                return await self._processar_consulta_sincrona(anos[0], dict_mes_numero[mes_inicio], dict_mes_numero[mes_fim])
                
        except ValueError as e:
            logger.error(f"Erro de validação na consulta Playwright: {e}")
            raise e
        except Exception as e:
            logger.error(f"Erro inesperado na consulta Playwright: {e}", exc_info=True)
            raise e
    
    async def _processar_consulta_sincrona(self, ano: int, mes_inicio: str, mes_fim: str) -> Dict[str, Any]:
        """
        Processa uma consulta síncrona para um único ano.
        
        Args:
            ano: Ano para consulta.
            mes_inicio: Mês inicial.
            mes_fim: Mês final.
            
        Returns:
            Dados da consulta.
        """
        logger.info(f"Processando consulta síncrona Playwright para ano {ano}")
        
        with TimerContext(f"consulta_sincrona_playwright_{ano}") as timer:
            scraper = TransparenciaPlaywrightScraper(headless=True)
            dados = await scraper.obter_dados_transparencia(ano, mes_inicio, mes_fim)
        
        # Registra métricas
        performance_tracker.criar_metrica(
            endpoint="consulta_playwright",
            operation="consulta_sincrona",
            ano_inicio=ano,
            ano_fim=ano,
            mes_inicio=mes_inicio,
            mes_fim=mes_fim,
            tempo_total=timer.get_duration(),
            tempo_scraping=timer.get_duration(),
            numero_registros=len(dados) if dados else 0,
            sucesso=True
        )
        
        resultado = {
            "dados": dados or [],
            "total_registros": len(dados) if dados else 0,
            "anos_processados": [ano],
            "tempo_execucao": timer.get_duration(),
            "tipo_scraper": "playwright",
            "modo": "sincrono"
        }
        
        logger.info(f"Consulta síncrona Playwright concluída: {resultado['total_registros']} registros em {timer.get_duration():.2f}s")
        return resultado
    
    async def _processar_consulta_assincrona(self, anos: List[int], mes_inicio: str, mes_fim: str, background_tasks: BackgroundTasks) -> Dict[str, Any]:
        """
        Inicia uma consulta assíncrona para múltiplos anos.
        
        Args:
            anos: Lista de anos para consulta.
            mes_inicio: Mês inicial.
            mes_fim: Mês final.
            background_tasks: Tarefas em background.
            
        Returns:
            ID da consulta para acompanhamento.
        """
        # Gera ID único para a consulta
        id_consulta = f"playwright_{uuid.uuid4().hex[:8]}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Registra a consulta no repositório
        range_anos = (min(anos), max(anos))
        self.repository.iniciar_consulta(id_consulta, range_anos)
        
        # Adiciona a tarefa ao background
        background_tasks.add_task(
            self._executar_consulta_background,
            id_consulta, anos, mes_inicio, mes_fim
        )
        
        logger.info(f"Consulta assíncrona Playwright iniciada: {id_consulta} para anos {anos}")
        
        return {
            "id_consulta": id_consulta,
            "status": "processando",
            "mensagem": f"Consulta Playwright iniciada para {len(anos)} anos",
            "anos_solicitados": anos,
            "tipo_scraper": "playwright",
            "modo": "assincrono"
        }
    
    async def _executar_consulta_background(self, id_consulta: str, anos: List[int], mes_inicio: str, mes_fim: str):
        """
        Executa a consulta em background de forma assíncrona.
        
        Args:
            id_consulta: ID da consulta.
            anos: Lista de anos.
            mes_inicio: Mês inicial.
            mes_fim: Mês final.
        """
        try:
            logger.info(f"[{id_consulta}] Iniciando processamento assíncrono Playwright para {len(anos)} anos")
            
            with TimerContext(f"consulta_assincrona_playwright_{id_consulta}") as timer_total:
                # Processa cada ano individualmente para melhor controle
                for ano in anos:
                    try:
                        self.repository.atualizar_status_processando(
                            id_consulta, 
                            f"Processando ano {ano} com Playwright..."
                        )
                        
                        with TimerContext(f"ano_{ano}_playwright") as timer_ano:
                            scraper = TransparenciaPlaywrightScraper(headless=True)
                            dados_ano = await scraper.obter_dados_transparencia(ano, mes_inicio, mes_fim)
                        
                        # Adiciona os resultados ao repositório
                        self.repository.adicionar_resultados_ano(
                            id_consulta, 
                            ano, 
                            dados_ano or [], 
                            timer_ano.get_duration()
                        )
                        
                        # Registra métrica individual
                        performance_tracker.criar_metrica(
                            endpoint="consulta_playwright",
                            operation="consulta_assincrona",
                            ano_inicio=ano,
                            ano_fim=ano,
                            mes_inicio=mes_inicio,
                            mes_fim=mes_fim,
                            tempo_total=timer_ano.get_duration(),
                            tempo_scraping=timer_ano.get_duration(),
                            numero_registros=len(dados_ano) if dados_ano else 0,
                            sucesso=True
                        )
                        
                        logger.info(f"[{id_consulta}] Ano {ano} processado: {len(dados_ano) if dados_ano else 0} registros")
                        
                    except Exception as e:
                        logger.error(f"[{id_consulta}] Erro ao processar ano {ano}: {e}")
                        self.repository.adicionar_erro_ano(id_consulta, ano, str(e))
            
            # Finaliza a consulta
            self.repository.finalizar_consulta_sucesso(id_consulta)
            
            # Registra métrica geral
            consulta_final = self.repository.obter_consulta(id_consulta)
            performance_tracker.criar_metrica(
                endpoint="consulta_playwright",
                operation="consulta_assincrona",
                ano_inicio=min(anos),
                ano_fim=max(anos),
                mes_inicio=mes_inicio,
                mes_fim=mes_fim,
                tempo_total=timer_total.get_duration(),
                tempo_scraping=timer_total.get_duration(),
                numero_registros=consulta_final["total_registros"],
                sucesso=True
            )
            
            logger.info(f"[{id_consulta}] Consulta Playwright concluída: {consulta_final['total_registros']} registros em {timer_total.get_duration():.2f}s")
            
        except Exception as e:
            logger.error(f"[{id_consulta}] Erro fatal na consulta Playwright: {e}", exc_info=True)
            self.repository.finalizar_consulta_erro(id_consulta, str(e))
    
    def obter_status_consulta(self, id_consulta: str) -> Dict[str, Any]:
        """
        Obtém o status de uma consulta.
        
        Args:
            id_consulta: ID da consulta.
            
        Returns:
            Status da consulta.
        """
        consulta = self.repository.obter_consulta(id_consulta)
        
        if not consulta:
            return {"error": f"Consulta {id_consulta} não encontrada"}
        
        resultado = {
            "id_consulta": id_consulta,
            "status": consulta["status"],
            "mensagem": consulta["mensagem"],
            "total_registros": consulta["total_registros"],
            "tipo_scraper": "playwright"
        }
        
        # Adiciona dados se a consulta estiver concluída
        if consulta["status"] == "concluido":
            resultado["dados"] = consulta["dados"]
            resultado["tempo_total"] = consulta["metricas"]["tempo_total"]
            resultado["estatisticas"] = self.repository.obter_estatisticas_consulta(id_consulta)
        
        # Adiciona erro se houver
        if consulta["status"] == "erro":
            resultado["erro"] = consulta.get("erro", "Erro desconhecido")
        
        return resultado
    
    def listar_consultas_ativas(self) -> List[Dict[str, Any]]:
        """
        Lista todas as consultas Playwright ativas.
        
        Returns:
            Lista com informações das consultas ativas.
        """
        ids_ativos = self.repository.listar_consultas_ativas()
        consultas = []
        
        for id_consulta in ids_ativos:
            consulta = self.repository.obter_consulta(id_consulta)
            if consulta:
                consultas.append({
                    "id_consulta": id_consulta,
                    "status": consulta["status"],
                    "mensagem": consulta["mensagem"],
                    "total_registros": consulta["total_registros"],
                    "anos_pendentes": len(consulta["anos_pendentes"]),
                    "anos_concluidos": len(consulta["anos_concluidos"]),
                    "tipo_scraper": "playwright"
                })
        
        return consultas
    
    def obter_estatisticas_consulta(self, id_consulta: str) -> Optional[Dict[str, Any]]:
        """
        Obtém estatísticas detalhadas de uma consulta.
        
        Args:
            id_consulta: ID da consulta.
            
        Returns:
            Estatísticas da consulta ou None se não encontrada.
        """
        return self.repository.obter_estatisticas_consulta(id_consulta)
    
    def limpar_consultas_antigas(self, horas: int = 24) -> int:
        """
        Remove consultas antigas do repositório.
        
        Args:
            horas: Idade máxima das consultas em horas.
            
        Returns:
            Número de consultas removidas.
        """
        return self.repository.limpar_consultas_antigas(horas)
