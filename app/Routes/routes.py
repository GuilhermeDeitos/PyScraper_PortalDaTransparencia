from fastapi import APIRouter, Response, status, BackgroundTasks, HTTPException
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

def convert_numpy_types(obj):
    """Converte tipos numpy para tipos Python nativos"""
    import numpy as np
    
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif pd.isna(obj):
        return None
    else:
        return obj

@router.get("/performance-metrics", 
           summary="Obtém métricas de performance da API")
async def obter_metricas_performance(response: Response):
    """Obtém as métricas de performance coletadas durante as consultas"""
    try:
        # Verifica se o arquivo existe
        metrics_file = "performance_metrics.csv"
        if not os.path.exists(metrics_file):
            return {"error": "Nenhuma métrica encontrada"}
        
        # Lê o arquivo CSV
        df = pd.read_csv(metrics_file)
        
        if df.empty:
            return {"error": "Nenhuma métrica encontrada"}
        
        # Converte colunas de tempo para numérico se necessário
        if 'tempo_total_segundos' not in df.columns and 'tempo_total' in df.columns:
            df['tempo_total_segundos'] = pd.to_numeric(df['tempo_total'], errors='coerce')
        elif 'tempo_total_segundos' in df.columns:
            df['tempo_total_segundos'] = pd.to_numeric(df['tempo_total_segundos'], errors='coerce')
        
        # Estatísticas básicas
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
    """Obtém um resumo estatístico das métricas de performance"""
    try:
        # Verifica se o arquivo existe
        metrics_file = "performance_metrics.csv"
        if not os.path.exists(metrics_file):
            return {"error": "Nenhuma métrica encontrada"}
        
        # Lê o arquivo CSV
        df = pd.read_csv(metrics_file)
        
        if df.empty:
            return {"error": "Nenhuma métrica encontrada"}
        
        # Converte timestamp para datetime se não estiver
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Converte tempo total para segundos se necessário
        if 'tempo_total_segundos' not in df.columns and 'tempo_total' in df.columns:
            df['tempo_total_segundos'] = pd.to_numeric(df['tempo_total'], errors='coerce')
        
        # Filtra apenas consultas concluídas (síncronas e assíncronas finais)
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
        
        # Verifica se o ano está na lista de anos processados
        anos_concluidos = consulta_completa.get("anos_concluidos", [])
        anos_pendentes = consulta_completa.get("anos_pendentes", [])
        
        # Converte ano para string para comparação
        ano_str = str(ano)
        
        # Verifica se o ano ainda está pendente
        if ano in anos_pendentes and ano not in anos_concluidos:
            raise HTTPException(
                status_code=202, 
                detail=f"Ano {ano} ainda está sendo processado"
            )
        
        # Verifica se o ano foi processado
        if ano not in anos_concluidos:
            raise HTTPException(
                status_code=404, 
                detail=f"Ano {ano} não foi encontrado ou não está no escopo da consulta"
            )
        
        # Busca dados do ano específico
        dados_parciais_por_ano = consulta_completa.get("dados_parciais_por_ano", {})
        resumo_por_ano = consulta_completa.get("resumo_por_ano", {})
        
        # Verifica se temos dados para o ano (pode estar como string ou int)
        dados_ano = None
        resumo_ano = None
        
        # Tenta buscar como string primeiro
        if ano_str in dados_parciais_por_ano:
            dados_ano = dados_parciais_por_ano[ano_str]
        elif str(ano) in resumo_por_ano:
            # Se não tem dados parciais, mas tem resumo, busca pelos períodos
            resumo_ano = resumo_por_ano[str(ano)]
        
        # Tenta buscar como int se não encontrou como string
        if not dados_ano and ano in dados_parciais_por_ano:
            dados_ano = dados_parciais_por_ano[ano]
        elif not resumo_ano and ano in resumo_por_ano:
            resumo_ano = resumo_por_ano[ano]
        
        # Se encontrou dados diretos do ano
        if dados_ano:
            return {
                "ano": ano,
                "dados": dados_ano.get("dados", []),
                "total_registros": dados_ano.get("total_registros", 0),
                "periodos_processados": dados_ano.get("periodos", []),
                "processado_em": dados_ano.get("processado_em"),
                "status_consulta": consulta_completa["status"],
                "fonte_dados": "dados_parciais_por_ano"
            }
        
        # Se não tem dados diretos, reconstrói pelos períodos
        elif resumo_ano:
            # Busca dados pelos períodos individuais
            dados_por_periodo = consulta_completa.get("dados_parciais_por_periodo", {})
            periodos_processados = resumo_ano.get("periodos_processados", [])
            
            dados_consolidados = []
            for periodo in periodos_processados:
                if periodo in dados_por_periodo:
                    dados_periodo = dados_por_periodo[periodo].get("dados", [])
                    dados_consolidados.extend(dados_periodo)
            
            return {
                "ano": ano,
                "dados": dados_consolidados,
                "total_registros": len(dados_consolidados),
                "periodos_processados": periodos_processados,
                "processado_em": resumo_ano.get("processado_em"),
                "status_consulta": consulta_completa["status"],
                "fonte_dados": "reconstruido_por_periodos"
            }
        
        # Se chegou até aqui, não encontrou dados
        raise HTTPException(
            status_code=404, 
            detail=f"Dados do ano {ano} não encontrados, mesmo estando marcado como processado"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter dados do ano {ano} para consulta {id_consulta}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/consulta/{id_consulta}/periodo/{ano}/{mes}")
async def obter_dados_periodo(id_consulta: str, ano: int, mes: int):
    """Obtém os dados de um período específico (ano/mês) de uma consulta"""
    try:
        consulta_completa = consulta_service.consulta_repo.obter_consulta(id_consulta)
        
        if "error" in consulta_completa:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        # Formata o período
        periodo = f"{ano}-{mes:02d}"
        
        # Verifica se o período está concluído
        periodos_concluidos = consulta_completa.get("periodos_concluidos", [])
        periodos_pendentes = consulta_completa.get("periodos_pendentes", [])
        
        if periodo in periodos_pendentes and periodo not in periodos_concluidos:
            raise HTTPException(
                status_code=202, 
                detail=f"Período {periodo} ainda está sendo processado"
            )
        
        if periodo not in periodos_concluidos:
            raise HTTPException(
                status_code=404, 
                detail=f"Período {periodo} não foi encontrado ou não está no escopo da consulta"
            )
        
        # Busca dados do período específico
        dados_por_periodo = consulta_completa.get("dados_parciais_por_periodo", {})
        resumo_por_periodo = consulta_completa.get("resumo_por_periodo", {})
        
        if periodo in dados_por_periodo:
            dados_periodo = dados_por_periodo[periodo]
            return {
                "periodo": periodo,
                "ano": ano,
                "mes": mes,
                "dados": dados_periodo.get("dados", []),
                "total_registros": dados_periodo.get("total_registros", 0),
                "processado_em": dados_periodo.get("processado_em"),
                "status_consulta": consulta_completa["status"]
            }
        
        # Se não encontrou dados, mas tem resumo
        elif periodo in resumo_por_periodo:
            resumo = resumo_por_periodo[periodo]
            return {
                "periodo": periodo,
                "ano": ano,
                "mes": mes,
                "dados": [],  # Dados não disponíveis no resumo
                "total_registros": resumo.get("total_registros", 0),
                "processado_em": resumo.get("processado_em"),
                "status_consulta": consulta_completa["status"],
                "observacao": "Apenas resumo disponível, dados detalhados não encontrados"
            }
        
        raise HTTPException(
            status_code=404, 
            detail=f"Dados do período {periodo} não encontrados"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter dados do período {ano}-{mes:02d} para consulta {id_consulta}: {e}")
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
            "total_anos": len(set(anos_concluidos + anos_pendentes)),
            "detalhes_por_ano": {}
        }
        
        # Adicionar detalhes para anos concluídos
        for ano in anos_concluidos:
            ano_key = str(ano)
            resumo_ano = resumo_por_ano.get(ano_key, resumo_por_ano.get(ano, {}))
            
            response["detalhes_por_ano"][ano] = {
                "status": "concluido",
                "total_registros": resumo_ano.get("total_registros", 0),
                "processado_em": resumo_ano.get("processado_em"),
                "periodos_processados": resumo_ano.get("periodos_processados", []),
                "tem_dados": resumo_ano.get("tem_dados", False),
                "endpoint_dados": f"/consulta/{id_consulta}/ano/{ano}"
            }
        
        # Adicionar detalhes para anos pendentes
        for ano in anos_pendentes:
            if ano not in anos_concluidos:  # Evita duplicação
                response["detalhes_por_ano"][ano] = {
                    "status": "pendente",
                    "total_registros": 0,
                    "processado_em": None,
                    "periodos_processados": [],
                    "tem_dados": False,
                    "endpoint_dados": None
                }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter anos disponíveis para consulta {id_consulta}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/consulta/{id_consulta}/periodos-disponiveis")
async def obter_periodos_disponiveis(id_consulta: str):
    """Lista os períodos disponíveis e seus status em uma consulta"""
    try:
        consulta_completa = consulta_service.consulta_repo.obter_consulta(id_consulta)
        
        if "error" in consulta_completa:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        periodos_concluidos = consulta_completa.get("periodos_concluidos", [])
        periodos_pendentes = consulta_completa.get("periodos_pendentes", [])
        resumo_por_periodo = consulta_completa.get("resumo_por_periodo", {})
        
        response = {
            "id_consulta": id_consulta,
            "status_geral": consulta_completa["status"],
            "periodos_concluidos": periodos_concluidos,
            "periodos_pendentes": periodos_pendentes,
            "total_periodos": len(set(periodos_concluidos + periodos_pendentes)),
            "detalhes_por_periodo": {}
        }
        
        # Adicionar detalhes para períodos concluídos
        for periodo in periodos_concluidos:
            resumo_periodo = resumo_por_periodo.get(periodo, {})
            ano = resumo_periodo.get("ano")
            mes = resumo_periodo.get("mes")
            
            response["detalhes_por_periodo"][periodo] = {
                "status": "concluido",
                "ano": ano,
                "mes": mes,
                "total_registros": resumo_periodo.get("total_registros", 0),
                "processado_em": resumo_periodo.get("processado_em"),
                "tem_dados": resumo_periodo.get("tem_dados", False),
                "endpoint_dados": f"/consulta/{id_consulta}/periodo/{ano}/{mes}" if ano and mes else None
            }
        
        # Adicionar detalhes para períodos pendentes
        for periodo in periodos_pendentes:
            if periodo not in periodos_concluidos:  # Evita duplicação
                # Extrai ano e mês do formato YYYY-MM
                try:
                    ano, mes = periodo.split('-')
                    ano, mes = int(ano), int(mes)
                except:
                    ano, mes = None, None
                
                response["detalhes_por_periodo"][periodo] = {
                    "status": "pendente",
                    "ano": ano,
                    "mes": mes,
                    "total_registros": 0,
                    "processado_em": None,
                    "tem_dados": False,
                    "endpoint_dados": None
                }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter períodos disponíveis para consulta {id_consulta}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system-status")
async def get_system_status_endpoint():
    """Obtém status atual do sistema de scrapers"""
    return get_system_status()