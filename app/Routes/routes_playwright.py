from fastapi import APIRouter, Response, status, BackgroundTasks
from app.Models.Schema import ConsultaParams
from app.Services.consulta_playwright_service import ConsultaPlaywrightService
from app.utils.performance_tracker import performance_tracker
import logging
import pandas as pd
import os

logger = logging.getLogger(__name__)
router = APIRouter()
consulta_playwright_service = ConsultaPlaywrightService()

@router.post("/consultar-playwright", 
            summary="Consulta dados do Portal da Transparência usando Playwright",
            response_description="Dados de despesas do período solicitado via Playwright")
async def consultar_playwright(body: ConsultaParams, response: Response, background_tasks: BackgroundTasks):
    """
    Consulta dados do Portal da Transparência usando Playwright.
    
    Este endpoint utiliza Playwright para automação web assíncrona, oferecendo:
    - Melhor performance para consultas de múltiplos anos
    - Processamento assíncrono automático para consultas com mais de 1 ano
    - Maior estabilidade e confiabilidade
    - Suporte nativo a operações assíncronas
    
    Args:
        body: Parâmetros da consulta (data_inicio, data_fim)
        background_tasks: Tarefas em background do FastAPI
        
    Returns:
        - Para 1 ano: Dados completos da consulta
        - Para múltiplos anos: ID da consulta para acompanhamento assíncrono
    """
    try:
        resultado = await consulta_playwright_service.processar_consulta(body, background_tasks)
        
        # Define status code baseado no tipo de resultado
        if "id_consulta" in resultado:
            response.status_code = status.HTTP_202_ACCEPTED
        else:
            response.status_code = status.HTTP_200_OK
        
        return resultado
    except ValueError as e:
        logger.error(f"Erro de validação Playwright: {str(e)}")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Erro interno Playwright: {str(e)}", exc_info=True)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": f"Erro interno: {str(e)}"}

@router.get("/status-consulta-playwright/{id_consulta}", 
           summary="Verifica o status de uma consulta Playwright em andamento")
async def verificar_status_consulta_playwright(id_consulta: str, response: Response):
    """
    Verifica o status de uma consulta Playwright.
    
    Args:
        id_consulta: ID da consulta retornado pelo endpoint /consultar-playwright
        
    Returns:
        Status atual da consulta, incluindo:
        - Status: processando, concluido, erro
        - Mensagem de progresso
        - Dados (se concluída)
        - Estatísticas detalhadas (se concluída)
    """
    resultado = consulta_playwright_service.obter_status_consulta(id_consulta)
    
    if "error" in resultado:
        response.status_code = status.HTTP_404_NOT_FOUND
    elif resultado.get("status") == "concluido":
        response.status_code = status.HTTP_200_OK
    elif resultado.get("status") == "erro":
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        response.status_code = status.HTTP_202_ACCEPTED
    
    return resultado

@router.get("/consultas-ativas-playwright", 
           summary="Lista todas as consultas Playwright ativas")
async def listar_consultas_ativas_playwright():
    """
    Lista todas as consultas Playwright que estão sendo processadas.
    
    Returns:
        Lista de consultas ativas com informações de progresso
    """
    try:
        consultas = consulta_playwright_service.listar_consultas_ativas()
        return {
            "consultas_ativas": consultas,
            "total": len(consultas),
            "tipo_scraper": "playwright"
        }
    except Exception as e:
        logger.error(f"Erro ao listar consultas ativas Playwright: {e}")
        return {"error": str(e)}

@router.get("/estatisticas-consulta-playwright/{id_consulta}",
           summary="Obtém estatísticas detalhadas de uma consulta Playwright")
async def obter_estatisticas_consulta_playwright(id_consulta: str, response: Response):
    """
    Obtém estatísticas detalhadas de uma consulta Playwright.
    
    Args:
        id_consulta: ID da consulta
        
    Returns:
        Estatísticas detalhadas incluindo:
        - Tempos de execução por ano
        - Número de registros por ano
        - Métricas de performance
        - Comparativos de eficiência
    """
    try:
        estatisticas = consulta_playwright_service.obter_estatisticas_consulta(id_consulta)
        
        if not estatisticas:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"error": f"Consulta {id_consulta} não encontrada"}
        
        return estatisticas
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas Playwright: {e}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": str(e)}

@router.delete("/limpar-consultas-antigas-playwright",
              summary="Remove consultas Playwright antigas do sistema")
async def limpar_consultas_antigas_playwright(horas: int = 24):
    """
    Remove consultas Playwright concluídas ou com erro há mais de X horas.
    
    Args:
        horas: Idade máxima das consultas a manter (padrão: 24 horas)
        
    Returns:
        Número de consultas removidas
    """
    try:
        removidas = consulta_playwright_service.limpar_consultas_antigas(horas)
        return {
            "mensagem": f"Limpeza concluída",
            "consultas_removidas": removidas,
            "criterio_horas": horas,
            "tipo_scraper": "playwright"
        }
    except Exception as e:
        logger.error(f"Erro ao limpar consultas antigas Playwright: {e}")
        return {"error": str(e)}

@router.get("/metricas-playwright",
           summary="Obtém métricas consolidadas do Playwright")
async def obter_metricas_playwright():
    """
    Obtém métricas consolidadas de performance do Playwright.
    
    Returns:
        Métricas de performance incluindo:
        - Tempo médio por consulta
        - Registros processados
        - Taxa de sucesso
        - Comparativos com Selenium
    """
    try:
        # Obtém métricas do performance tracker
        metricas_consulta_sincrona = performance_tracker.get_metric_stats("consulta_sincrona_playwright")
        metricas_consulta_assincrona = performance_tracker.get_metric_stats("consulta_assincrona_playwright")
        metricas_por_ano = performance_tracker.get_metric_stats("consulta_ano_playwright")
        
        # Consultas ativas
        consultas_ativas = consulta_playwright_service.listar_consultas_ativas()
        
        resultado = {
            "tipo_scraper": "playwright",
            "consultas_ativas": len(consultas_ativas),
            "metricas_sincronas": metricas_consulta_sincrona,
            "metricas_assincronas": metricas_consulta_assincrona,
            "metricas_por_ano": metricas_por_ano,
            "consultas_em_andamento": consultas_ativas
        }
        
        return resultado
        
    except Exception as e:
        logger.error(f"Erro ao obter métricas Playwright: {e}")
        return {"error": str(e)}

@router.get("/comparacao-selenium-playwright",
           summary="Compara métricas entre Selenium e Playwright")
async def comparar_selenium_playwright():
    """
    Compara métricas de performance entre Selenium e Playwright.
    
    Returns:
        Comparação detalhada incluindo:
        - Tempos de execução médios
        - Taxa de sucesso
        - Registros processados
        - Eficiência relativa
    """
    try:
        # Métricas Playwright
        playwright_sincrona = performance_tracker.get_metric_stats("consulta_sincrona_playwright")
        playwright_assincrona = performance_tracker.get_metric_stats("consulta_assincrona_playwright")
        playwright_ano = performance_tracker.get_metric_stats("consulta_ano_playwright")
        
        # Métricas Selenium (assumindo que existem métricas similares)
        selenium_sincrona = performance_tracker.get_metric_stats("consulta_sincrona")
        selenium_assincrona = performance_tracker.get_metric_stats("consulta_assincrona")
        selenium_ano = performance_tracker.get_metric_stats("consulta_ano")
        
        comparacao = {
            "consultas_sincronas": {
                "playwright": playwright_sincrona,
                "selenium": selenium_sincrona
            },
            "consultas_assincronas": {
                "playwright": playwright_assincrona,
                "selenium": selenium_assincrona
            },
            "processamento_por_ano": {
                "playwright": playwright_ano,
                "selenium": selenium_ano
            }
        }
        
        # Calcula métricas comparativas se ambos têm dados
        if (playwright_sincrona and selenium_sincrona and 
            playwright_sincrona.get("count", 0) > 0 and selenium_sincrona.get("count", 0) > 0):
            
            tempo_medio_pw = playwright_sincrona.get("avg_tempo_execucao", 0)
            tempo_medio_sel = selenium_sincrona.get("avg_tempo_execucao", 0)
            
            if tempo_medio_sel > 0:
                melhoria_tempo = ((tempo_medio_sel - tempo_medio_pw) / tempo_medio_sel) * 100
                comparacao["melhoria_playwright"] = {
                    "tempo_execucao_percent": round(melhoria_tempo, 2),
                    "mais_rapido": tempo_medio_pw < tempo_medio_sel
                }
        
        return comparacao
        
    except Exception as e:
        logger.error(f"Erro ao comparar Selenium e Playwright: {e}")
        return {"error": str(e)}
