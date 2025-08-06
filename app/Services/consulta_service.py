import os
from fastapi import BackgroundTasks
import threading
import uuid
import logging
import time
import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Semaphore
from app.Models.Schema import ConsultaParams
from app.Repositories.consulta_repo import ConsultaRepository
from app.Services.scrapper_service import TransparenciaScraper
from app.utils.validators import validar_parametros
from app.utils.date_utils import dict_mes_numero
from app.utils.performance_tracker import performance_tracker, TimerContext

logger = logging.getLogger(__name__)

# Configuração para controle de concorrência
MAX_CONCURRENT_SCRAPERS = 3  # Máximo de scrapers simultâneos
SCRAPER_SEMAPHORE = Semaphore(MAX_CONCURRENT_SCRAPERS)

# Pool global de threads para scrapers
SCRAPER_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SCRAPERS, thread_name_prefix="ScraperThread")

class ConsultaService:
    def __init__(self):
        self.consulta_repo = ConsultaRepository()
        # Cada consulta não mantém mais uma instância de scraper
        
    async def processar_consulta(self, params: ConsultaParams, background_tasks: BackgroundTasks):
        """Processa uma consulta de dados do Portal da Transparência"""
        inicio_total = time.time()
        
        mes_inicio, ano_inicio, mes_fim, ano_fim = validar_parametros(
            params.data_inicio, params.data_fim
        )
        
        # Verifica se há slots disponíveis para processamento
        slots_disponiveis = SCRAPER_SEMAPHORE._value
        total_periodos = self._calcular_total_periodos(ano_inicio, mes_inicio, ano_fim, mes_fim)
                
        if ano_inicio != ano_fim:
            # Processamento assíncrono para múltiplos anos
            id_consulta = str(uuid.uuid4())
            
            # Inicializa o registro da consulta com parâmetros mensais
            self.consulta_repo.iniciar_consulta(
                id_consulta, 
                anos_range=(ano_inicio, ano_fim),
                mes_inicio=mes_inicio,
                mes_fim=mes_fim
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
            
            tempo_configuracao = time.time() - inicio_total
            
            # Registra métrica para consulta assíncrona (tempo apenas da configuração inicial)
            metrica = performance_tracker.criar_metrica(
                endpoint="/consultar",
                operation="consulta_assincrona_inicio",
                ano_inicio=ano_inicio,
                ano_fim=ano_fim,
                mes_inicio=mes_inicio,
                mes_fim=mes_fim,
                tempo_total=tempo_configuracao,
                numero_registros=0,
                sucesso=True,
                id_consulta=id_consulta
            )
            performance_tracker.salvar_metrica(metrica)
            
            # Mensagem informativa sobre recursos
            mensagem_recursos = self._gerar_mensagem_recursos(slots_disponiveis, total_periodos)
            
            return {
                "status": "processando",
                "mensagem": f"Consulta para o período {mes_inicio:02d}/{ano_inicio} a {mes_fim:02d}/{ano_fim} iniciada em background",
                "id_consulta": id_consulta,
                "consultar_status": f"/status-consulta/{id_consulta}",
                "total_periodos": total_periodos,
                "slots_disponiveis": slots_disponiveis,
                "max_concurrent_scrapers": MAX_CONCURRENT_SCRAPERS,
                "info_recursos": mensagem_recursos
            }
        else:
            # Processamento síncrono para um único ano (com controle de concorrência)
            try:
                inicio_scraper = time.time()
                
                # Verifica se há recursos suficientes para processamento síncrono
                if slots_disponiveis == 0:
                    # Se não há slots disponíveis, força processamento assíncrono
                    id_consulta = str(uuid.uuid4())
                    
                    self.consulta_repo.iniciar_consulta(
                        id_consulta, 
                        anos_range=(ano_inicio, ano_fim),
                        mes_inicio=mes_inicio,
                        mes_fim=mes_fim
                    )
                    
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
                        "mensagem": f"Todos os slots estão ocupados. Consulta movida para processamento assíncrono",
                        "id_consulta": id_consulta,
                        "consultar_status": f"/status-consulta/{id_consulta}",
                        "total_periodos": total_periodos,
                        "slots_disponiveis": 0,
                        "max_concurrent_scrapers": MAX_CONCURRENT_SCRAPERS,
                        "motivo_assincrono": "recursos_esgotados"
                    }
                
                # Para um único ano, processa por períodos mensais
                dados_por_periodo = {}
                total_registros = 0
                
                for mes in range(mes_inicio, mes_fim + 1):
                    # Usa o semáforo para controlar concorrência
                    with SCRAPER_SEMAPHORE:
                        resultado_mes = self._executar_scraper_com_retry(ano_inicio, mes, mes)
                    
                    periodo = f"{ano_inicio}-{mes:02d}"
                    dados_por_periodo[periodo] = {
                        "dados": resultado_mes,
                        "total_registros": len(resultado_mes) if resultado_mes else 0,
                        "ano": ano_inicio,
                        "mes": mes
                    }
                    total_registros += len(resultado_mes) if resultado_mes else 0
                
                fim_scraper = time.time()
                
                tempo_total = time.time() - inicio_total
                tempo_scraping = fim_scraper - inicio_scraper
                
                # Registra métrica para consulta síncrona
                metrica = performance_tracker.criar_metrica(
                    endpoint="/consultar",
                    operation="consulta_sincrona",
                    ano_inicio=ano_inicio,
                    ano_fim=ano_fim,
                    mes_inicio=mes_inicio,
                    mes_fim=mes_fim,
                    tempo_total=tempo_total,
                    tempo_scraping=tempo_scraping,
                    numero_registros=total_registros,
                    sucesso=True
                )
                performance_tracker.salvar_metrica(metrica)
                
                # Consolida dados para compatibilidade
                dados_consolidados = []
                for periodo_dados in dados_por_periodo.values():
                    dados_consolidados.extend(periodo_dados["dados"])
                
                return {
                    "dados": dados_consolidados,
                    "total_registros": total_registros,
                    "dados_por_periodo": dados_por_periodo,
                    "processamento": "sincrono",
                    "slots_utilizados": min(total_periodos, MAX_CONCURRENT_SCRAPERS)
                }
                
            except Exception as e:
                tempo_total = time.time() - inicio_total
                # Registra métrica para erro
                metrica = performance_tracker.criar_metrica(
                    endpoint="/consultar",
                    operation="consulta_sincrona",
                    ano_inicio=ano_inicio,
                    ano_fim=ano_fim,
                    mes_inicio=mes_inicio,
                    mes_fim=mes_fim,
                    tempo_total=tempo_total,
                    numero_registros=0,
                    sucesso=False,
                    erro_descricao=str(e)
                )
                performance_tracker.salvar_metrica(metrica)
                raise
    
    def _processar_em_background(self, id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim):
        """Inicia processamento em background usando o pool de threads"""
        # Submete a tarefa ao pool de threads global
        future = SCRAPER_EXECUTOR.submit(
            self._executar_consulta_por_periodos,
            id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim
        )
        
        # Log informativo
        thread_name = threading.current_thread().name
        logger.info(f"Consulta {id_consulta} submetida ao pool de threads para período {mes_inicio:02d}/{ano_inicio} a {mes_fim:02d}/{ano_fim}")
        
        # Adiciona callback para log de conclusão
        def log_completion(future):
            try:
                future.result()  # Isso vai lançar exceção se houver erro
                logger.info(f"Consulta {id_consulta} concluída com sucesso")
            except Exception as e:
                logger.error(f"Consulta {id_consulta} falhou: {e}")
        
        future.add_done_callback(log_completion)
    
    def _executar_consulta_por_periodos(self, id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim):
        """Executa consulta processando período por período (mês/ano)"""
        inicio_total = time.time()
        thread_name = threading.current_thread().name
        
        try:
            total_registros = 0
            tempo_scraping_total = 0.0
            
            # Gera todos os períodos que devem ser processados
            periodos_para_processar = self._gerar_lista_periodos(ano_inicio, mes_inicio, ano_fim, mes_fim)
            
            logger.info(f"[{thread_name}] Iniciando processamento de {len(periodos_para_processar)} períodos para consulta {id_consulta}")
            
            for idx, (ano, mes) in enumerate(periodos_para_processar, 1):
                periodo = f"{ano}-{mes:02d}"
                
                # Atualiza status com informação de progresso e thread
                progresso = f"{idx}/{len(periodos_para_processar)}"
                slots_disponiveis = SCRAPER_SEMAPHORE._value
                
                self.consulta_repo.atualizar_status_processando(
                    id_consulta, 
                    f"[{thread_name}] Aguardando slot para período {periodo} ({progresso}) - Slots disponíveis: {slots_disponiveis}"
                )
                
                # Controla concorrência com semáforo
                with SCRAPER_SEMAPHORE:
                    self.consulta_repo.atualizar_status_processando(
                        id_consulta, 
                        f"[{thread_name}] Processando período {periodo} ({progresso})"
                    )
                    
                    try:
                        # Executa o scraper para o período específico com medição de tempo
                        inicio_scraper_periodo = time.time()
                        resultado_periodo = self._executar_scraper_com_retry(ano, mes, mes)
                        fim_scraper_periodo = time.time()
                        
                        tempo_scraper_periodo = fim_scraper_periodo - inicio_scraper_periodo
                        registros_periodo = len(resultado_periodo) if resultado_periodo else 0
                        total_registros += registros_periodo
                        tempo_scraping_total += tempo_scraper_periodo
                        
                        # Registra métrica para cada período processado
                        metrica_periodo = performance_tracker.criar_metrica(
                            endpoint="/consultar",
                            operation="consulta_assincrona_periodo",
                            ano_inicio=ano,
                            ano_fim=ano,
                            mes_inicio=mes,
                            mes_fim=mes,
                            tempo_total=tempo_scraper_periodo,
                            tempo_scraping=tempo_scraper_periodo,
                            numero_registros=registros_periodo,
                            sucesso=True,
                            id_consulta=id_consulta
                        )
                        performance_tracker.salvar_metrica(metrica_periodo)
                        
                        # Registra resultados por período
                        self.consulta_repo.adicionar_resultados_periodo(
                            id_consulta, ano, mes, resultado_periodo
                        )
                        
                        logger.info(f"[{thread_name}] Período {periodo} processado: {registros_periodo} registros em {tempo_scraper_periodo:.2f}s ({progresso})")
                        
                    except Exception as e:
                        logger.error(f"[{thread_name}] Erro ao processar período {periodo}: {e}")
                        
                        # Registra métrica para erro do período
                        metrica_erro_periodo = performance_tracker.criar_metrica(
                            endpoint="/consultar",
                            operation="consulta_assincrona_periodo",
                            ano_inicio=ano,
                            ano_fim=ano,
                            mes_inicio=mes,
                            mes_fim=mes,
                            tempo_total=0.0,
                            numero_registros=0,
                            sucesso=False,
                            erro_descricao=str(e),
                            id_consulta=id_consulta
                        )
                        performance_tracker.salvar_metrica(metrica_erro_periodo)
                        
                        self.consulta_repo.registrar_erro_periodo(id_consulta, ano, mes, str(e))
            
            tempo_total_final = time.time() - inicio_total
            
            # Finaliza a consulta como concluída
            self.consulta_repo.finalizar_consulta(id_consulta)
            
            # Registra métrica final da consulta completa
            metrica_final = performance_tracker.criar_metrica(
                endpoint="/consultar",
                operation="consulta_assincrona_final",
                ano_inicio=ano_inicio,
                ano_fim=ano_fim,
                mes_inicio=mes_inicio,
                mes_fim=mes_fim,
                tempo_total=tempo_total_final,
                tempo_scraping=tempo_scraping_total,
                numero_registros=total_registros,
                sucesso=True,
                id_consulta=id_consulta
            )
            performance_tracker.salvar_metrica(metrica_final)
            
            logger.info(f"[{thread_name}] Consulta {id_consulta} concluída: {total_registros} registros em {tempo_total_final:.2f}s")
            
        except Exception as e:
            tempo_total_final = time.time() - inicio_total
            logger.error(f"[{thread_name}] Erro na execução da consulta {id_consulta}: {e}", exc_info=True)
            
            # Registra métrica para erro geral
            metrica_erro_geral = performance_tracker.criar_metrica(
                endpoint="/consultar",
                operation="consulta_assincrona_final",
                ano_inicio=ano_inicio,
                ano_fim=ano_fim,
                mes_inicio=mes_inicio,
                mes_fim=mes_fim,
                tempo_total=tempo_total_final,
                numero_registros=0,
                sucesso=False,
                erro_descricao=str(e),
                id_consulta=id_consulta
            )
            performance_tracker.salvar_metrica(metrica_erro_geral)
            
            self.consulta_repo.registrar_erro_consulta(id_consulta, str(e))
    
    def _executar_scraper_com_retry(self, ano, mes, mes_fim, max_retries=2):
        """Executa scraper com retry em caso de erro - cada chamada cria sua própria instância"""
        last_exception = None
        thread_name = threading.current_thread().name
        
        for tentativa in range(max_retries + 1):
            scraper_service = None
            try:
                # Cria uma nova instância do scraper para cada tentativa
                logger.debug(f"[{thread_name}] Criando scraper para período {ano}-{mes:02d} (tentativa {tentativa + 1})")
                scraper_service = TransparenciaScraper(headless=True)
                resultado = scraper_service.executar_scraper(ano, mes, mes_fim)
                logger.debug(f"[{thread_name}] Scraper concluído para período {ano}-{mes:02d}")
                return resultado
                
            except Exception as e:
                last_exception = e
                logger.warning(f"[{thread_name}] Tentativa {tentativa + 1}/{max_retries + 1} falhou para período {ano}-{mes:02d}: {e}")
                
                # Garante que o scraper seja limpo em caso de erro
                if scraper_service:
                    try:
                        scraper_service.__del__()
                    except:
                        pass
                
                if tentativa < max_retries:
                    # Aguarda antes da próxima tentativa com backoff exponencial
                    wait_time = (tentativa + 1) * 2
                    logger.info(f"[{thread_name}] Aguardando {wait_time}s antes da próxima tentativa...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"[{thread_name}] Todas as tentativas falharam para período {ano}-{mes:02d}")
        
        # Se chegou aqui, todas as tentativas falharam
        if last_exception:
            raise last_exception
        else:
            raise Exception(f"Falha ao processar período {ano}-{mes:02d} após {max_retries + 1} tentativas")
    
    def _calcular_total_periodos(self, ano_inicio, mes_inicio, ano_fim, mes_fim):
        """Calcula o total de períodos que serão processados"""
        if ano_inicio == ano_fim:
            return mes_fim - mes_inicio + 1
        else:
            total = 0
            # Primeiro ano
            total += 13 - mes_inicio
            # Anos intermediários
            total += (ano_fim - ano_inicio - 1) * 12
            # Último ano
            total += mes_fim
            return total
    
    def _gerar_mensagem_recursos(self, slots_disponiveis, total_periodos):
        """Gera mensagem informativa sobre recursos disponíveis"""
        if slots_disponiveis == 0:
            return "Todos os slots de processamento estão ocupados. Sua consulta será enfileirada."
        elif slots_disponiveis < total_periodos:
            tempo_estimado = (total_periodos / MAX_CONCURRENT_SCRAPERS) * 30  # Estimativa de 30s por período
            return f"Processamento paralelo com {slots_disponiveis} slots. Tempo estimado: {tempo_estimado:.0f}s"
        else:
            return f"Recursos suficientes disponíveis. Processamento otimizado com até {min(slots_disponiveis, total_periodos)} slots."
    
    def _gerar_lista_periodos(self, ano_inicio, mes_inicio, ano_fim, mes_fim):
        """Gera lista de períodos (ano, mês) para processar"""
        periodos = []
        
        if ano_inicio == ano_fim:
            # Mesmo ano: apenas os meses especificados
            for mes in range(mes_inicio, mes_fim + 1):
                periodos.append((ano_inicio, mes))
        else:
            # Múltiplos anos
            # Primeiro ano: do mês inicial até dezembro
            for mes in range(mes_inicio, 13):
                periodos.append((ano_inicio, mes))
            
            # Anos intermediários: todos os meses
            for ano in range(ano_inicio + 1, ano_fim):
                for mes in range(1, 13):
                    periodos.append((ano, mes))
            
            # Último ano: de janeiro até o mês final
            for mes in range(1, mes_fim + 1):
                periodos.append((ano_fim, mes))
        
        return periodos
    
    def obter_status_consulta(self, id_consulta):
        """Obtém o status atual de uma consulta"""
        return self.consulta_repo.obter_consulta(id_consulta)
    
    def obter_dados_ano_especifico(self, id_consulta, ano):
        """Obtém dados de um ano específico de uma consulta"""
        consulta = self.consulta_repo.obter_consulta(id_consulta)
        
        if "error" in consulta:
            return consulta
        
        # Busca dados do ano específico
        dados_por_ano = consulta.get("dados_por_ano", {})
        if str(ano) in dados_por_ano:
            return {
                "ano": ano,
                "dados": dados_por_ano[str(ano)]["dados"],
                "total_registros": dados_por_ano[str(ano)]["total_registros"],
                "periodos": dados_por_ano[str(ano)].get("periodos", [])
            }
        
        return {"error": f"Dados do ano {ano} não encontrados ou ainda não processados"}
    
    def obter_dados_periodo_especifico(self, id_consulta, ano, mes):
        """Obtém dados de um período específico de uma consulta"""
        consulta = self.consulta_repo.obter_consulta(id_consulta)
        
        if "error" in consulta:
            return consulta
        
        # Busca dados do período específico
        periodo = f"{ano}-{mes:02d}"
        dados_por_periodo = consulta.get("dados_por_periodo", {})
        
        if periodo in dados_por_periodo:
            return {
                "periodo": periodo,
                "ano": ano,
                "mes": mes,
                "dados": dados_por_periodo[periodo]["dados"],
                "total_registros": dados_por_periodo[periodo]["total_registros"]
            }
        
        return {"error": f"Dados do período {periodo} não encontrados ou ainda não processados"}

def get_system_status():
    """Função utilitária para obter status do sistema"""
    return {
        "max_concurrent_scrapers": MAX_CONCURRENT_SCRAPERS,
        "slots_disponiveis": SCRAPER_SEMAPHORE._value,
        "slots_ocupados": MAX_CONCURRENT_SCRAPERS - SCRAPER_SEMAPHORE._value,
        "threads_ativas": threading.active_count(),
        "pool_info": {
            "max_workers": SCRAPER_EXECUTOR._max_workers,
            "threads_count": len(SCRAPER_EXECUTOR._threads) if hasattr(SCRAPER_EXECUTOR, '_threads') else 0
        }
    }