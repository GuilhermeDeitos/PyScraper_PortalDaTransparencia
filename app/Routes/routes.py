from http.client import HTTPException
from fastapi import APIRouter, Response, status, BackgroundTasks
from app.Models.Schema import ConsultaParams
from app.Services.consulta_service import ConsultaService, get_system_status
from app.utils.performance_tracker import performance_tracker
import logging
import pandas as pd
import os

logger = logging.getLogger(__name__)
router = APIRouter()
consulta_service = ConsultaService()

@router.post("/consultar", 
            summary="Consulta dados do Portal da Transparência",
            response_description="Dados de despesas do período solicitado")
async def consultar(body: ConsultaParams, response: Response, background_tasks: BackgroundTasks):
    try:
        resultado = await consulta_service.processar_consulta(body, background_tasks)
        
        # Define status code baseado no tipo de resultado
        if "id_consulta" in resultado:
            response.status_code = status.HTTP_202_ACCEPTED
        else:
            response.status_code = status.HTTP_200_OK
        
        return resultado
    except ValueError as e:
        logger.error(f"Erro de validação: {str(e)}")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Erro interno: {str(e)}", exc_info=True)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": f"Erro interno: {str(e)}"}

@router.get("/status-consulta/{id_consulta}")
async def obter_status_consulta(id_consulta: str):
    """Obtém o status de uma consulta em andamento com dados parciais"""
    consulta = consulta_service.consulta_repo.obter_consulta(id_consulta)
    
    if "error" in consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    
    # Adicionar links para dados parciais se disponíveis
    if consulta["status"] == "processando" and consulta.get("dados_parciais"):
        consulta["endpoints_dados_parciais"] = {
            "anos_disponiveis": f"/consulta/{id_consulta}/anos-disponiveis",
            "dados_por_ano": {
                ano: f"/consulta/{id_consulta}/ano/{ano}" 
                for ano in consulta.get("anos_concluidos", [])
            }
        }
    
    return consulta

@router.get("/performance-metrics", 
           summary="Obtém métricas de performance da API")
async def obter_metricas_performance(response: Response):
    """
    Retorna as métricas de performance salvas no arquivo CSV.
    Inclui estatísticas resumidas e os dados brutos.
    """
    try:
        csv_path = performance_tracker.csv_path
        
        if not os.path.exists(csv_path):
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"error": "Arquivo de métricas não encontrado"}
        
        # Lê o arquivo CSV
        df = pd.read_csv(csv_path)
        
        if df.empty:
            return {
                "estatisticas": {"total_consultas": 0},
                "metricas": []
            }
        
        def convert_numpy_types(obj):
            """Converte tipos numpy/pandas para tipos Python nativos"""
            if obj is None or pd.isna(obj):
                return None
            elif hasattr(obj, 'item'):  # Tipos numpy
                return obj.item()
            elif isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
                return str(obj)
            elif isinstance(obj, bool):
                return bool(obj)
            elif isinstance(obj, (int, float)):
                return int(obj) if isinstance(obj, int) else float(obj)
            elif hasattr(obj, 'dtype'):  # Outros tipos pandas/numpy
                try:
                    return obj.item()
                except (ValueError, AttributeError):
                    return str(obj)
            else:
                return obj
        
        # Calcula estatísticas resumidas
        estatisticas = {
            "total_consultas": convert_numpy_types(len(df)),
            "consultas_bem_sucedidas": convert_numpy_types(len(df[df['sucesso'] == True])),
            "consultas_com_erro": convert_numpy_types(len(df[df['sucesso'] == False])),
            "tempo_medio_segundos": convert_numpy_types(df['tempo_total_segundos'].mean()),
            "tempo_maximo_segundos": convert_numpy_types(df['tempo_total_segundos'].max()),
            "tempo_minimo_segundos": convert_numpy_types(df['tempo_total_segundos'].min()),
            "total_registros_processados": convert_numpy_types(df['numero_registros'].sum()),
            "operacoes_por_tipo": {str(k): convert_numpy_types(v) for k, v in df['operation'].value_counts().to_dict().items()}
        }
        
        # Estatísticas por ano
        if 'ano_inicio' in df.columns:
            tempo_por_ano = df.groupby('ano_inicio')['tempo_total_segundos'].mean().to_dict()
            registros_por_ano = df.groupby('ano_inicio')['numero_registros'].sum().to_dict()
            
            estatisticas["tempo_medio_por_ano"] = {str(k): convert_numpy_types(v) for k, v in tempo_por_ano.items()}
            estatisticas["registros_por_ano"] = {str(k): convert_numpy_types(v) for k, v in registros_por_ano.items()}
        
        # Converte DataFrame para lista de dicionários e trata tipos numpy
        metricas = df.to_dict('records')
        
        # Converte tipos numpy para tipos Python nativos
        for metrica in metricas:
            for key, value in metrica.items():
                metrica[key] = convert_numpy_types(value)
        
        return {
            "estatisticas": estatisticas,
            "metricas": metricas
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter métricas de performance: {e}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": f"Erro ao processar métricas: {str(e)}"}

@router.get("/performance-summary", 
           summary="Obtém resumo estatístico das métricas de performance")
async def obter_resumo_performance(response: Response):
    """
    Retorna apenas um resumo estatístico das métricas, sem os dados brutos.
    Útil para dashboards e monitoramento.
    """
    try:
        csv_path = performance_tracker.csv_path
        
        if not os.path.exists(csv_path):
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"error": "Arquivo de métricas não encontrado"}
        
        df = pd.read_csv(csv_path)
        
        if df.empty:
            return {"total_consultas": 0}
        
        def convert_numpy_types(obj):
            """Converte tipos numpy/pandas para tipos Python nativos"""
            if obj is None or pd.isna(obj):
                return None
            elif hasattr(obj, 'item'):  # Tipos numpy
                return obj.item()
            elif isinstance(obj, (pd.Timestamp, pd.DatetimeIndex)):
                return str(obj)
            elif isinstance(obj, bool):
                return bool(obj)
            elif isinstance(obj, (int, float)):
                return int(obj) if isinstance(obj, int) else float(obj)
            elif hasattr(obj, 'dtype'):  # Outros tipos pandas/numpy
                try:
                    return obj.item()
                except (ValueError, AttributeError):
                    return str(obj)
            else:
                return obj
        
        # Filtra apenas consultas concluídas (não as de início de processo assíncrono)
        df_concluidas = df[df['operation'].isin(['consulta_sincrona', 'consulta_assincrona_final'])]
        
        resumo = {
            "periodo_analise": {
                "data_inicio": str(df['timestamp'].min()),
                "data_fim": str(df['timestamp'].max())
            },
            "consultas": {
                "total": convert_numpy_types(len(df_concluidas)),
                "bem_sucedidas": convert_numpy_types(len(df_concluidas[df_concluidas['sucesso'] == True])),
                "com_erro": convert_numpy_types(len(df_concluidas[df_concluidas['sucesso'] == False])),
                "taxa_sucesso_percentual": convert_numpy_types((len(df_concluidas[df_concluidas['sucesso'] == True]) / len(df_concluidas) * 100) if len(df_concluidas) > 0 else 0)
            },
            "performance": {
                "tempo_medio_segundos": round(convert_numpy_types(df_concluidas['tempo_total_segundos'].mean()), 2),
                "tempo_mediano_segundos": round(convert_numpy_types(df_concluidas['tempo_total_segundos'].median()), 2),
                "tempo_maximo_segundos": round(convert_numpy_types(df_concluidas['tempo_total_segundos'].max()), 2),
                "tempo_minimo_segundos": round(convert_numpy_types(df_concluidas['tempo_total_segundos'].min()), 2),
                "desvio_padrao_segundos": round(convert_numpy_types(df_concluidas['tempo_total_segundos'].std()), 2)
            },
            "dados": {
                "total_registros_processados": convert_numpy_types(df_concluidas['numero_registros'].sum()),
                "media_registros_por_consulta": round(convert_numpy_types(df_concluidas['numero_registros'].mean()), 2),
                "registros_por_segundo_medio": round(convert_numpy_types(df_concluidas['numero_registros'].sum() / df_concluidas['tempo_total_segundos'].sum()), 2) if convert_numpy_types(df_concluidas['tempo_total_segundos'].sum()) > 0 else 0
            },
            "tipos_operacao": {str(k): convert_numpy_types(v) for k, v in df['operation'].value_counts().to_dict().items()}
        }
        
        return resumo
        
    except Exception as e:
        logger.error(f"Erro ao obter resumo de performance: {e}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": f"Erro ao processar resumo: {str(e)}"}

@router.get("/consulta/{id_consulta}/ano/{ano}")
async def obter_dados_ano(id_consulta: str, ano: int):
    """Obtém os dados de um ano específico de uma consulta"""
    try:
        consulta_completa = consulta_service.consulta_repo.obter_consulta(id_consulta)
        
        if "error" in consulta_completa:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        # Verificar se o ano foi processado
        dados_por_ano = consulta_completa.get("dados_parciais") or consulta_completa.get("dados_por_ano", {})
        
        if ano not in dados_por_ano:
            if ano in consulta_completa.get("anos_pendentes", []):
                raise HTTPException(
                    status_code=202, 
                    detail=f"Ano {ano} ainda está sendo processado"
                )
            else:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Ano {ano} não encontrado na consulta"
                )
        
        dados_ano = dados_por_ano[ano]
        return {
            "ano": ano,
            "dados": dados_ano["dados"],
            "total_registros": dados_ano["total_registros"],
            "processado_em": dados_ano.get("processado_em"),
            "status_consulta": consulta_completa["status"]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/consulta/{id_consulta}/anos-disponiveis")
async def obter_anos_disponiveis(id_consulta: str):
    """Lista os anos disponíveis e seus status em uma consulta"""
    try:
        consulta_completa = consulta_service.consulta_repo.obter_consulta(id_consulta)
        
        if "error" in consulta_completa:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        anos_concluidos = consulta_completa.get("anos_concluidos", [])
        anos_pendentes = consulta_completa.get("anos_pendentes", [])
        resumo_por_ano = consulta_completa.get("resumo_por_ano", {})
        
        response = {
            "id_consulta": id_consulta,
            "status_geral": consulta_completa["status"],
            "anos_concluidos": anos_concluidos,
            "anos_pendentes": anos_pendentes,
            "total_anos": len(anos_concluidos) + len(anos_pendentes),
            "detalhes_por_ano": {}
        }
        
        # Adicionar detalhes para anos concluídos
        for ano in anos_concluidos:
            ano_int = int(ano)
            response["detalhes_por_ano"][ano_int] = {
                "status": "concluido",
                "total_registros": resumo_por_ano.get(ano_int, {}).get("total_registros", 0),
                "processado_em": resumo_por_ano.get(ano_int, {}).get("processado_em"),
                "endpoint_dados": f"/consulta/{id_consulta}/ano/{ano_int}"
            }
        
        # Adicionar detalhes para anos pendentes
        for ano in anos_pendentes:
            ano_int = int(ano)
            response["detalhes_por_ano"][ano_int] = {
                "status": "pendente",
                "total_registros": 0,
                "processado_em": None,
                "endpoint_dados": None
            }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system-status")
async def get_system_status_endpoint():
    """Obtém status atual do sistema de scrapers"""
    return get_system_status()