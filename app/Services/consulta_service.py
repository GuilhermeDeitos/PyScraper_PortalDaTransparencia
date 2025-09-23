import os
import random
from typing import Any, Dict, List
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
from threading import Lock
import weakref

logger = logging.getLogger(__name__)

# Configuração para controle de concorrência
MAX_CONCURRENT_SCRAPERS = 8  # Máximo de scrapers simultâneos
SCRAPER_SEMAPHORE = Semaphore(MAX_CONCURRENT_SCRAPERS)
ano_locks = weakref.WeakValueDictionary()
ano_locks_creation_lock = Lock()

# Pool global de threads para scrapers
SCRAPER_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_CONCURRENT_SCRAPERS, thread_name_prefix="ScraperThread")

def get_lock_for_ano(ano: int) -> Lock:
    """Obtém ou cria um lock para um ano específico"""
    with ano_locks_creation_lock:
        # Tenta obter o lock existente
        lock = ano_locks.get(ano)
        if lock is None:
            # Se não existe, cria um novo
            lock = Lock()
            ano_locks[ano] = lock
        return lock
    
class ConsultaService:
    def __init__(self):
        self.consulta_repo = ConsultaRepository()
        self.consultas_canceladas = set()
        
    def cancelar_consulta(self, id_consulta):
        """Marca uma consulta para cancelamento"""
        logger.info(f"Marcando consulta {id_consulta} para cancelamento")
        self.consultas_canceladas.add(id_consulta)
        self.consulta_repo.atualizar_status_processando(
            id_consulta, 
            f"Cancelamento solicitado pelo usuário"
        )
        return {"status": "cancelamento_solicitado"}
        
    def _validar_dados_ano(self, dados: List[Dict[str, Any]], ano: int) -> List[Dict[str, Any]]:
        """
        Valida e corrige dados de um ano específico.
        
        Args:
            dados: Lista de dados a validar
            ano: Ano esperado dos dados
            
        Returns:
            Lista de dados validados
        """
        dados_validos = []
        registros_invalidos = 0
        
        for registro in dados:
            # Verificar se os campos críticos estão corretos
            valido = True
            
            # Verificar campo GRUPO_NATUREZA_DESPESA
            if "GRUPO_NATUREZA_DESPESA" in registro:
                valor = registro["GRUPO_NATUREZA_DESPESA"]
                # Se contém texto de origem, está invertido
                if isinstance(valor, str) and (valor.startswith("O -") or valor.startswith("T -")):
                    logger.warning(f"Registro com campos invertidos detectado para ano {ano}")
                    valido = False
                    registros_invalidos += 1
            
            # Verificar se ORIGEM_RECURSOS contém valores numéricos quando não deveria
            if "ORIGEM_RECURSOS" in registro:
                valor = str(registro["ORIGEM_RECURSOS"])
                # Se é puramente numérico e grande, provavelmente é um valor monetário
                if valor.replace(".", "").replace(",", "").isdigit() and len(valor) > 4:
                    logger.warning(f"ORIGEM_RECURSOS com valor numérico suspeito: {valor}")
                    valido = False
                    registros_invalidos += 1
            
            if valido:
                # Adicionar ano ao registro para rastreamento
                registro['_ano_validado'] = ano
                dados_validos.append(registro)
        
        if registros_invalidos > 0:
            logger.warning(f"Detectados {registros_invalidos} registros inválidos de {len(dados)} para ano {ano}")
        
        return dados_validos
        
    async def processar_consulta(self, params: ConsultaParams, background_tasks: BackgroundTasks):
        """Processa uma consulta de dados do Portal da Transparência organizando por ano"""
        inicio_total = time.time()
        
        mes_inicio, ano_inicio, mes_fim, ano_fim = validar_parametros(
            params.data_inicio, params.data_fim
        )
        
        # Verifica se há slots disponíveis para processamento
        slots_disponiveis = SCRAPER_SEMAPHORE._value
        total_anos = ano_fim - ano_inicio + 1
                
        if ano_inicio != ano_fim:
            # Processamento assíncrono para múltiplos anos
            id_consulta = str(uuid.uuid4())
            
            # Inicializa o registro da consulta organizando por anos
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
            mensagem_recursos = self._gerar_mensagem_recursos(slots_disponiveis, total_anos)
            
            return {
                "status": "processando",
                "mensagem": f"Consulta para o período {mes_inicio:02d}/{ano_inicio} a {mes_fim:02d}/{ano_fim} iniciada em background",
                "id_consulta": id_consulta,
                "consultar_status": f"/status-consulta/{id_consulta}",
                "total_anos": total_anos,
                "slots_disponiveis": slots_disponiveis,
                "max_concurrent_scrapers": MAX_CONCURRENT_SCRAPERS,
                "info_recursos": mensagem_recursos
            }
        else:
            # Processamento síncrono para um único ano
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
                        "total_anos": total_anos,
                        "slots_disponiveis": 0,
                        "max_concurrent_scrapers": MAX_CONCURRENT_SCRAPERS,
                        "motivo_assincrono": "recursos_esgotados"
                    }
                
                # Para um único ano, processa o ano completo
                with SCRAPER_SEMAPHORE:
                    resultado_ano = self._executar_scraper_com_retry(ano_inicio, mes_inicio, mes_fim, id_consulta=id_consulta)
                
                fim_scraper = time.time()
                
                tempo_total = time.time() - inicio_total
                tempo_scraping = fim_scraper - inicio_scraper
                total_registros = len(resultado_ano) if resultado_ano else 0
                
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
                
                # Organiza dados por ano (mesmo sendo um único ano)
                dados_por_ano = {
                    str(ano_inicio): {
                        "dados": resultado_ano,
                        "total_registros": total_registros,
                        "mes_inicio": mes_inicio,
                        "mes_fim": mes_fim,
                        "processado_em": time.strftime("%Y-%m-%d %H:%M:%S")
                    }
                }
                
                return {
                    "dados": resultado_ano,  # Mantém compatibilidade
                    "dados_por_ano": dados_por_ano,  # Nova estrutura por ano
                    "total_registros": total_registros,
                    "anos_processados": [ano_inicio],
                    "processamento": "sincrono",
                    "slots_utilizados": 1
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
            self._executar_consulta_por_anos,
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
    
    def _executar_consulta_por_anos(self, id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim):
        """Executa consulta processando ano por ano"""
        inicio_total = time.time()
        thread_name = threading.current_thread().name
        
        try:
            total_registros = 0
            tempo_scraping_total = 0.0
            
            # Verificar se já foi cancelada antes de começar
            if id_consulta in self.consultas_canceladas:
                logger.info(f"[{thread_name}] Consulta {id_consulta} já estava marcada como cancelada, interrompendo")
                self.consulta_repo.finalizar_consulta(id_consulta, status="cancelada")
                return
            
            # Gera todos os anos que devem ser processados
            anos_para_processar = list(range(ano_inicio, ano_fim + 1))
            
            logger.info(f"[{thread_name}] Iniciando processamento de {len(anos_para_processar)} anos para consulta {id_consulta}")
            
            for idx, ano in enumerate(anos_para_processar, 1):
                # Verificar cancelamento antes de cada ano
                if id_consulta in self.consultas_canceladas:
                    logger.info(f"[{thread_name}] Consulta {id_consulta} foi cancelada, interrompendo processamento")
                    self.consulta_repo.atualizar_status_processando(
                        id_consulta, 
                        f"Processamento cancelado pelo usuário após processar {idx-1} de {len(anos_para_processar)} anos"
                    )
                    break
                # Determina o período para o ano atual
                ano_lock = get_lock_for_ano(ano)
                
                if not ano_lock.acquire(blocking=False):
                    logger.warning(f"[{thread_name}] Ano {ano} já está sendo processado por outra thread, pulando...")
                    self.consulta_repo.registrar_erro_ano(
                        id_consulta, ano, 
                        "Ano já está sendo processado por outra consulta"
                    )
                    continue

                if ano == ano_inicio and ano == ano_fim:
                    # Mesmo ano: usar mês específico de início e fim
                    mes_inicial_ano = mes_inicio
                    mes_final_ano = mes_fim
                elif ano == ano_inicio:
                    # Primeiro ano: do mês específico até dezembro
                    mes_inicial_ano = mes_inicio
                    mes_final_ano = 12
                elif ano == ano_fim:
                    # Último ano: de janeiro até mês específico
                    mes_inicial_ano = 1
                    mes_final_ano = mes_fim
                else:
                    # Anos intermediários: ano completo
                    mes_inicial_ano = 1
                    mes_final_ano = 12
                
                # Atualiza status com informação de progresso e thread
                progresso = f"{idx}/{len(anos_para_processar)}"
                slots_disponiveis = SCRAPER_SEMAPHORE._value
                
                self.consulta_repo.atualizar_status_processando(
                    id_consulta, 
                    f"[{thread_name}] Aguardando slot para ano {ano} ({progresso}) - Slots disponíveis: {slots_disponiveis}"
                )
                
                # Controla concorrência com semáforo
                with SCRAPER_SEMAPHORE:
                    self.consulta_repo.atualizar_status_processando(
                        id_consulta, 
                        f"[{thread_name}] Processando ano {ano} (meses {mes_inicial_ano:02d}-{mes_final_ano:02d}) ({progresso})"
                    )
                    
                    try:
                        # Executa o scraper para o ano específico com medição de tempo
                        inicio_scraper_ano = time.time()
                        resultado_ano = self._executar_scraper_com_retry(ano, mes_inicial_ano, mes_final_ano, id_consulta=id_consulta)
                        fim_scraper_ano = time.time()
                        
                        tempo_scraper_ano = fim_scraper_ano - inicio_scraper_ano
                        registros_ano = len(resultado_ano) if resultado_ano else 0
                        total_registros += registros_ano
                        tempo_scraping_total += tempo_scraper_ano
                        
                        # Registra métrica para cada ano processado
                        metrica_ano = performance_tracker.criar_metrica(
                            endpoint="/consultar",
                            operation="consulta_assincrona_ano",
                            ano_inicio=ano,
                            ano_fim=ano,
                            mes_inicio=mes_inicial_ano,
                            mes_fim=mes_final_ano,
                            tempo_total=tempo_scraper_ano,
                            tempo_scraping=tempo_scraper_ano,
                            numero_registros=registros_ano,
                            sucesso=True,
                            id_consulta=id_consulta
                        )
                        performance_tracker.salvar_metrica(metrica_ano)
                        
                        # Registra resultados por ano
                        self.consulta_repo.adicionar_resultados_ano(
                            id_consulta, ano, resultado_ano, mes_inicial_ano, mes_final_ano
                        )
                        
                        logger.info(f"[{thread_name}] Ano {ano} processado: {registros_ano} registros em {tempo_scraper_ano:.2f}s ({progresso})")
                        
                    except Exception as e:
                        logger.error(f"[{thread_name}] Erro ao processar ano {ano}: {e}")
                        
                        # Registra métrica para erro do ano
                        metrica_erro_ano = performance_tracker.criar_metrica(
                            endpoint="/consultar",
                            operation="consulta_assincrona_ano",
                            ano_inicio=ano,
                            ano_fim=ano,
                            mes_inicio=mes_inicial_ano,
                            mes_fim=mes_final_ano,
                            tempo_total=0.0,
                            numero_registros=0,
                            sucesso=False,
                            erro_descricao=str(e),
                            id_consulta=id_consulta
                        )
                        performance_tracker.salvar_metrica(metrica_erro_ano)
                        
                        self.consulta_repo.registrar_erro_ano(id_consulta, ano, str(e))
                    finally:
                        # Sempre liberar o lock do ano
                        ano_lock.release()
            
            tempo_total_final = time.time() - inicio_total
            
            # Verificar se foi cancelado antes de finalizar
            if id_consulta in self.consultas_canceladas:
                logger.info(f"[{thread_name}] Finalizando consulta {id_consulta} como cancelada")
                self.consulta_repo.finalizar_consulta(id_consulta, status="cancelada")
                # Limpar a consulta da lista de canceladas
                self.consultas_canceladas.remove(id_consulta)
            else:
                # Finaliza a consulta como concluída normalmente
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
    
    def _executar_scraper_com_retry(self, ano, mes_inicio, mes_fim, max_retries=2, id_consulta=None):
        """Executa scraper com retry e validação dos dados"""
        last_exception = None
        thread_name = threading.current_thread().name
        
        for tentativa in range(max_retries + 1):
            if id_consulta and id_consulta in self.consultas_canceladas:
                logger.info(f"[{thread_name}] Pulando scraper para ano {ano} - consulta {id_consulta} cancelada")
                raise Exception("Consulta cancelada pelo usuário")
            scraper_service = None
            try:
                logger.debug(f"[{thread_name}] Criando scraper para ano {ano} (tentativa {tentativa + 1})")
                scraper_service = TransparenciaScraper(headless=True)
                
                # Executar scraper
                resultado = scraper_service.executar_scraper(ano, dict_mes_numero[mes_inicio], dict_mes_numero[mes_fim])
                
                # Validar dados retornados
                if resultado:
                    resultado_validado = self._validar_dados_ano(resultado, ano)
                    
                    # Se muitos dados foram invalidados, tentar novamente
                    taxa_validade = len(resultado_validado) / len(resultado) if resultado else 0
                    if taxa_validade < 0.8:  # Menos de 80% válido
                        logger.warning(f"[{thread_name}] Taxa de validade baixa ({taxa_validade:.2%}) para ano {ano}")
                        if tentativa < max_retries:
                            raise Exception(f"Taxa de validade muito baixa: {taxa_validade:.2%}")
                    
                    logger.debug(f"[{thread_name}] Scraper concluído para ano {ano} - {len(resultado_validado)} registros válidos")
                    return resultado_validado
                else:
                    return []
                    
            except Exception as e:
                last_exception = e
                logger.warning(f"[{thread_name}] Tentativa {tentativa + 1}/{max_retries + 1} falhou para ano {ano}: {e}")
                
                if scraper_service:
                    try:
                        scraper_service.cleanup()
                    except:
                        pass
                
                if tentativa < max_retries:
                    wait_time = (tentativa + 1) * 3 + random.uniform(0, 2)
                    logger.info(f"[{thread_name}] Aguardando {wait_time:.1f}s antes da próxima tentativa...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"[{thread_name}] Todas as tentativas falharam para ano {ano}")
        
        if last_exception:
            raise last_exception
        else:
            raise Exception(f"Falha ao processar ano {ano} após {max_retries + 1} tentativas")
    
    def _gerar_mensagem_recursos(self, slots_disponiveis, total_anos):
        """Gera mensagem informativa sobre recursos disponíveis"""
        if slots_disponiveis == 0:
            return "Todos os slots de processamento estão ocupados. Sua consulta será enfileirada."
        elif slots_disponiveis < total_anos:
            tempo_estimado = (total_anos / MAX_CONCURRENT_SCRAPERS) * 60  # Estimativa de 60s por ano
            return f"Processamento paralelo com {slots_disponiveis} slots. Tempo estimado: {tempo_estimado:.0f}s"
        else:
            return f"Recursos suficientes disponíveis. Processamento otimizado com até {min(slots_disponiveis, total_anos)} slots."
    
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
                "mes_inicio": dados_por_ano[str(ano)].get("mes_inicio"),
                "mes_fim": dados_por_ano[str(ano)].get("mes_fim"),
                "processado_em": dados_por_ano[str(ano)].get("processado_em")
            }
        
        return {"error": f"Dados do ano {ano} não encontrados ou ainda não processados"}

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