import os
from fastapi import BackgroundTasks
import threading
import uuid
import logging
import time
from app.Models.Schema import ConsultaParams
from app.Repositories.consulta_repo import ConsultaRepository
from app.Services.scrapper_service import TransparenciaScraper
from app.utils.validators import validar_parametros
from app.utils.date_utils import dict_mes_numero
from app.utils.performance_tracker import performance_tracker, TimerContext

logger = logging.getLogger(__name__)

MAX_THREADS = os.cpu_count() or 4  # Define a quantidade máxima de threads

class ConsultaService:
    def __init__(self):
        self.consulta_repo = ConsultaRepository()
        self.scraper_service = TransparenciaScraper(headless=True)
    
    async def processar_consulta(self, params: ConsultaParams, background_tasks: BackgroundTasks):
        """Processa uma consulta de dados do Portal da Transparência"""
        inicio_total = time.time()
        
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
            
            tempo_configuracao = time.time() - inicio_total
            
            # Registra métrica para consulta assíncrona (tempo apenas da configuração inicial)
            metrica = performance_tracker.criar_metrica(
                endpoint="/consultar",
                operation="consulta_assincrona_inicio",
                ano_inicio=ano_inicio,
                ano_fim=ano_fim,
                mes_inicio=dict_mes_numero[mes_inicio],
                mes_fim=dict_mes_numero[mes_fim],
                tempo_total=tempo_configuracao,
                numero_registros=0,
                sucesso=True,
                id_consulta=id_consulta
            )
            performance_tracker.salvar_metrica(metrica)
            
            return {
                "status": "processando",
                "mensagem": f"Consulta para os anos {ano_inicio} a {ano_fim} iniciada em background",
                "id_consulta": id_consulta,
                "consultar_status": f"/status-consulta/{id_consulta}"
            }
        else:
            # Processamento síncrono para um único ano
            try:
                inicio_scraper = time.time()
                resultado = self.scraper_service.executar_scraper(
                    ano_inicio, 
                    dict_mes_numero[mes_inicio], 
                    dict_mes_numero[mes_fim]
                )
                fim_scraper = time.time()
                
                tempo_total = time.time() - inicio_total
                tempo_scraping = fim_scraper - inicio_scraper
                
                # Registra métrica para consulta síncrona
                metrica = performance_tracker.criar_metrica(
                    endpoint="/consultar",
                    operation="consulta_sincrona",
                    ano_inicio=ano_inicio,
                    ano_fim=ano_fim,
                    mes_inicio=dict_mes_numero[mes_inicio],
                    mes_fim=dict_mes_numero[mes_fim],
                    tempo_total=tempo_total,
                    tempo_scraping=tempo_scraping,
                    numero_registros=len(resultado) if resultado else 0,
                    sucesso=True
                )
                performance_tracker.salvar_metrica(metrica)
                
                return {
                    "dados": resultado,
                    "total_registros": len(resultado)
                }
                
            except Exception as e:
                tempo_total = time.time() - inicio_total
                # Registra métrica para erro
                metrica = performance_tracker.criar_metrica(
                    endpoint="/consultar",
                    operation="consulta_sincrona",
                    ano_inicio=ano_inicio,
                    ano_fim=ano_fim,
                    mes_inicio=dict_mes_numero[mes_inicio],
                    mes_fim=dict_mes_numero[mes_fim],
                    tempo_total=tempo_total,
                    numero_registros=0,
                    sucesso=False,
                    erro_descricao=str(e)
                )
                performance_tracker.salvar_metrica(metrica)
                raise
    
    def _processar_em_background(self, id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim):
        """Inicia thread para processamento em background"""
        #Definir o numero máximo de threads
        
        thread = threading.Thread(
            target=self._executar_consulta_sequencial,
            args=(id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim)
        )
        thread.daemon = True
        thread.start()
        logger.info(f"Consulta {id_consulta} iniciada em background para anos {ano_inicio} a {ano_fim} na thread {thread.name}")
    
    def _executar_consulta_sequencial(self, id_consulta, ano_inicio, mes_inicio, ano_fim, mes_fim):
        """Executa consulta sequencial para múltiplos anos"""
        inicio_total = time.time()
        
        try:
            total_registros = 0
            tempo_scraping_total = 0.0
            
            for ano in range(ano_inicio, ano_fim + 1):
                mes_inicial_ano = mes_inicio if ano == ano_inicio else 1
                mes_final_ano = mes_fim if ano == ano_fim else 12
                
                # Atualiza status
                self.consulta_repo.atualizar_status_processando(
                    id_consulta, 
                    f"Processando ano {ano} - {dict_mes_numero[mes_inicial_ano]} a {dict_mes_numero[mes_final_ano]}"
                )
                
                try:
                    # Executa o scraper para o ano com medição de tempo
                    inicio_scraper_ano = time.time()
                    resultado_ano = self.scraper_service.executar_scraper(
                        ano, 
                        dict_mes_numero[mes_inicial_ano], 
                        dict_mes_numero[mes_final_ano]
                    )
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
                        mes_inicio=dict_mes_numero[mes_inicial_ano],
                        mes_fim=dict_mes_numero[mes_final_ano],
                        tempo_total=tempo_scraper_ano,
                        tempo_scraping=tempo_scraper_ano,
                        numero_registros=registros_ano,
                        sucesso=True,
                        id_consulta=id_consulta
                    )
                    performance_tracker.salvar_metrica(metrica_ano)
                    
                    # Registra resultados
                    self.consulta_repo.adicionar_resultados_ano(
                        id_consulta, ano, resultado_ano
                    )
                    
                except Exception as e:
                    logger.error(f"Erro ao processar ano {ano}: {e}")
                    
                    # Registra métrica para erro do ano
                    metrica_erro_ano = performance_tracker.criar_metrica(
                        endpoint="/consultar",
                        operation="consulta_assincrona_ano",
                        ano_inicio=ano,
                        ano_fim=ano,
                        mes_inicio=dict_mes_numero[mes_inicial_ano],
                        mes_fim=dict_mes_numero[mes_final_ano],
                        tempo_total=0.0,
                        numero_registros=0,
                        sucesso=False,
                        erro_descricao=str(e),
                        id_consulta=id_consulta
                    )
                    performance_tracker.salvar_metrica(metrica_erro_ano)
                    
                    self.consulta_repo.registrar_erro_ano(id_consulta, ano, str(e))
            
            tempo_total_final = time.time() - inicio_total
            
            # Finaliza a consulta como concluída
            self.consulta_repo.finalizar_consulta(id_consulta)
            
            # Registra métrica final da consulta completa
            metrica_final = performance_tracker.criar_metrica(
                endpoint="/consultar",
                operation="consulta_assincrona_final",
                ano_inicio=ano_inicio,
                ano_fim=ano_fim,
                mes_inicio=dict_mes_numero[mes_inicio],
                mes_fim=dict_mes_numero[mes_fim],
                tempo_total=tempo_total_final,
                tempo_scraping=tempo_scraping_total,
                numero_registros=total_registros,
                sucesso=True,
                id_consulta=id_consulta
            )
            performance_tracker.salvar_metrica(metrica_final)
            
        except Exception as e:
            tempo_total_final = time.time() - inicio_total
            logger.error(f"Erro na execução da consulta {id_consulta}: {e}", exc_info=True)
            
            # Registra métrica para erro geral
            metrica_erro_geral = performance_tracker.criar_metrica(
                endpoint="/consultar",
                operation="consulta_assincrona_final",
                ano_inicio=ano_inicio,
                ano_fim=ano_fim,
                mes_inicio=dict_mes_numero[mes_inicio],
                mes_fim=dict_mes_numero[mes_fim],
                tempo_total=tempo_total_final,
                numero_registros=0,
                sucesso=False,
                erro_descricao=str(e),
                id_consulta=id_consulta
            )
            performance_tracker.salvar_metrica(metrica_erro_geral)
            
            self.consulta_repo.registrar_erro_consulta(id_consulta, str(e))
    
    def obter_status_consulta(self, id_consulta):
        """Obtém o status atual de uma consulta"""
        return self.consulta_repo.obter_consulta(id_consulta)