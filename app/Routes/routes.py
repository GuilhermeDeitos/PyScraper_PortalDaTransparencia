import asyncio
from fastapi import APIRouter, Response,Request, status, BackgroundTasks, HTTPException
from datetime import datetime
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
            summary="Consulta dados do Portal da Transparência organizados por ano",
            response_description="Dados de despesas do período solicitado organizados por ano")
async def consultar(request: Request, body: ConsultaParams, response: Response, background_tasks: BackgroundTasks):
    """
    Consulta dados do Portal da Transparência organizando os resultados por ano.
    
    Para consultas de um único ano: retorna resposta síncrona
    Para consultas de múltiplos anos: inicia processamento assíncrono
    """
    try:
        # Verificar se o cliente ainda está conectado
        if await request.is_disconnected():
            raise HTTPException(status_code=499, detail="Cliente desconectado")
        
        # Executar a consulta com verificação periódica de conexão
        resultado = await consulta_service.processar_consulta(
            body,
            background_tasks,
        )
        
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
        if isinstance(e, HTTPException) and e.status_code == 499:
            # Cliente desconectou, logar e retornar sem erro
            logger.info("Cliente desconectou durante consulta")
            return None
        logger.error(f"Erro interno: {str(e)}", exc_info=True)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": f"Erro interno: {str(e)}"}

@router.get("/status-consulta/{id_consulta}")
async def obter_status_consulta(id_consulta: str):
    """
    Obtém o status de uma consulta organizada por ano.
    
    Retorna informações sobre:
    - Status geral da consulta
    - Anos processados e pendentes
    - Dados parciais disponíveis por ano
    - Links para endpoints específicos
    """
    consulta = consulta_service.consulta_repo.obter_consulta(id_consulta)
    
    if "error" in consulta:
        raise HTTPException(status_code=404, detail="Consulta não encontrada")
    
    # Adicionar links para dados por ano se disponíveis
    if consulta.get("anos_concluidos"):
        consulta["endpoints_dados_por_ano"] = {
            "anos_disponiveis": f"/consulta/{id_consulta}/anos-disponiveis",
            "dados_por_ano": {
                str(ano): f"/consulta/{id_consulta}/ano/{ano}" 
                for ano in consulta.get("anos_concluidos", [])
            }
        }
    
    # Adicionar informações de progresso para consultas em processamento
    if consulta["status"] == "processando":
        total_anos = len(consulta.get("anos_concluidos", [])) + len(consulta.get("anos_pendentes", []))
        anos_processados = len(consulta.get("anos_concluidos", []))
        consulta["progresso"] = {
            "anos_processados": anos_processados,
            "total_anos": total_anos,
            "percentual_concluido": round((anos_processados / total_anos * 100), 2) if total_anos > 0 else 0
        }
    
    return consulta

@router.get("/consulta/{id_consulta}")
async def obter_consulta_completa(id_consulta: str):
    """
    Obtém todos os dados de uma consulta organizada por ano.
    
    Retorna a consulta completa com todos os anos processados.
    """
    try:
        consulta_completa = consulta_service.consulta_repo.obter_consulta(id_consulta)
        
        if "error" in consulta_completa:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        return consulta_completa
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter consulta completa {id_consulta}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/consulta/{id_consulta}/ano/{ano}")
async def obter_dados_ano(id_consulta: str, ano: int):
    """
    Obtém dados de um ano específico de uma consulta.
    
    Args:
        id_consulta: ID da consulta
        ano: Ano específico dos dados (ex: 2021)
    
    Returns:
        Dados completos do ano incluindo metadados
    """
    try:
        consulta_completa = consulta_service.consulta_repo.obter_consulta(id_consulta)
        
        if "error" in consulta_completa:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        # Verifica se o ano está na lista de anos processados
        anos_concluidos = consulta_completa.get("anos_concluidos", [])
        anos_pendentes = consulta_completa.get("anos_pendentes", [])
        
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
        
        # Busca dados do ano específico na nova estrutura
        dados_por_ano = consulta_completa.get("dados_por_ano", {})
        resumo_por_ano = consulta_completa.get("resumo_por_ano", {})
        
        # Tenta buscar o ano como string (formato padrão)
        ano_str = str(ano)
        
        if ano_str in dados_por_ano:
            dados_ano = dados_por_ano[ano_str]
            resumo_ano = resumo_por_ano.get(ano_str, {})
            
            return {
                "ano": ano,
                "dados": dados_ano.get("dados", []),
                "total_registros": dados_ano.get("total_registros", 0),
                "mes_inicio": dados_ano.get("mes_inicio"),
                "mes_fim": dados_ano.get("mes_fim"),
                "processado_em": dados_ano.get("processado_em"),
                "resumo_estatistico": resumo_ano,
                "metadata": {
                    "correcao_aplicada": dados_ano.get("correcao_aplicada", False),
                    "periodo_correcao": dados_ano.get("periodo_correcao"),
                    "tem_dados_originais": "dados_originais" in dados_ano
                },
                "status_consulta": consulta_completa["status"],
                "fonte_dados": "dados_por_ano"
            }
        
        # Se não encontrou na estrutura principal, verifica dados parciais
        dados_parciais_por_ano = consulta_completa.get("dados_parciais_por_ano", {})
        if ano_str in dados_parciais_por_ano:
            dados_ano = dados_parciais_por_ano[ano_str]
            
            return {
                "ano": ano,
                "dados": dados_ano.get("dados", []),
                "total_registros": dados_ano.get("total_registros", 0),
                "mes_inicio": dados_ano.get("mes_inicio"),
                "mes_fim": dados_ano.get("mes_fim"),
                "processado_em": dados_ano.get("processado_em"),
                "status_consulta": consulta_completa["status"],
                "fonte_dados": "dados_parciais",
                "observacao": "Dados parciais - consulta ainda em processamento"
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

@router.get("/consulta/{id_consulta}/anos-disponiveis")
async def obter_anos_disponiveis(id_consulta: str):
    """
    Lista os anos disponíveis e seus status em uma consulta organizada por ano.
    
    Returns:
        Informações detalhadas sobre cada ano processado ou pendente
    """
    try:
        consulta_completa = consulta_service.consulta_repo.obter_consulta(id_consulta)
        
        if "error" in consulta_completa:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        anos_concluidos = consulta_completa.get("anos_concluidos", [])
        anos_pendentes = consulta_completa.get("anos_pendentes", [])
        resumo_por_ano = consulta_completa.get("resumo_por_ano", {})
        dados_por_ano = consulta_completa.get("dados_por_ano", {})
        
        response = {
            "id_consulta": id_consulta,
            "status_geral": consulta_completa["status"],
            "organizacao": "por_ano",
            "anos_concluidos": sorted(anos_concluidos),
            "anos_pendentes": sorted(anos_pendentes),
            "total_anos": len(set(anos_concluidos + anos_pendentes)),
            "periodo_consulta": consulta_completa.get("periodo_consulta", {}),
            "detalhes_por_ano": {}
        }
        
        # Adicionar detalhes para anos concluídos
        for ano in anos_concluidos:
            ano_key = str(ano)
            resumo_ano = resumo_por_ano.get(ano_key, {})
            dados_ano = dados_por_ano.get(ano_key, {})
            
            response["detalhes_por_ano"][ano] = {
                "status": "concluido",
                "total_registros": dados_ano.get("total_registros", resumo_ano.get("total_registros", 0)),
                "mes_inicio": dados_ano.get("mes_inicio"),
                "mes_fim": dados_ano.get("mes_fim"),
                "processado_em": dados_ano.get("processado_em"),
                "tem_dados": len(dados_ano.get("dados", [])) > 0,
                "tem_resumo": bool(resumo_ano),
                "endpoint_dados": f"/consulta/{id_consulta}/ano/{ano}",
                "valores_totais": resumo_ano.get("valores_totais", {}),
                "unidades_orcamentarias": len(resumo_ano.get("unidades_orcamentarias", [])),
                "funcoes": len(resumo_ano.get("funcoes", []))
            }
        
        # Adicionar detalhes para anos pendentes
        for ano in anos_pendentes:
            if ano not in anos_concluidos:  # Evita duplicação
                response["detalhes_por_ano"][ano] = {
                    "status": "pendente",
                    "total_registros": 0,
                    "mes_inicio": None,
                    "mes_fim": None,
                    "processado_em": None,
                    "tem_dados": False,
                    "tem_resumo": False,
                    "endpoint_dados": None,
                    "observacao": "Processamento ainda não iniciado ou em andamento"
                }
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao obter anos disponíveis para consulta {id_consulta}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/system-status")
async def get_system_status_endpoint():
    """
    Obtém status atual do sistema de scrapers organizados por ano.
    
    Returns:
        Informações sobre recursos disponíveis e configuração do sistema
    """
    
    return get_system_status()

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

@router.get("/performance-metrics", 
           summary="Obtém métricas de performance da API organizadas por ano")
async def obter_metricas_performance(response: Response):
    """
    Retorna as métricas de performance salvas no arquivo CSV.
    Inclui estatísticas resumidas e os dados brutos organizados por ano.
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
                "metricas": [],
                "organizacao": "por_ano"
            }
        
        # Calcula estatísticas resumidas
        estatisticas = {
            "total_consultas": convert_numpy_types(len(df)),
            "consultas_bem_sucedidas": convert_numpy_types(len(df[df['sucesso'] == True])),
            "consultas_com_erro": convert_numpy_types(len(df[df['sucesso'] == False])),
            "tempo_medio_segundos": convert_numpy_types(df['tempo_total_segundos'].mean()),
            "tempo_maximo_segundos": convert_numpy_types(df['tempo_total_segundos'].max()),
            "tempo_minimo_segundos": convert_numpy_types(df['tempo_total_segundos'].min()),
            "total_registros_processados": convert_numpy_types(df['numero_registros'].sum()),
            "operacoes_por_tipo": {str(k): convert_numpy_types(v) for k, v in df['operation'].value_counts().to_dict().items()},
            "organizacao": "por_ano"
        }
        
        # Estatísticas por ano (organizadas por ano de processamento)
        if 'ano_inicio' in df.columns:
            # Estatísticas de processamento por ano
            tempo_por_ano = df.groupby('ano_inicio')['tempo_total_segundos'].agg(['mean', 'count', 'sum']).to_dict()
            registros_por_ano = df.groupby('ano_inicio')['numero_registros'].sum().to_dict()
            
            estatisticas["processamento_por_ano"] = {
                "tempo_medio_por_ano": {str(k): convert_numpy_types(v) for k, v in tempo_por_ano['mean'].items()},
                "consultas_por_ano": {str(k): convert_numpy_types(v) for k, v in tempo_por_ano['count'].items()},
                "tempo_total_por_ano": {str(k): convert_numpy_types(v) for k, v in tempo_por_ano['sum'].items()},
                "registros_por_ano": {str(k): convert_numpy_types(v) for k, v in registros_por_ano.items()}
            }
        
        # Análise de consultas por múltiplos anos vs ano único
        consultas_unicas = df[df['operation'] == 'consulta_sincrona']
        consultas_multiplas = df[df['operation'].isin(['consulta_assincrona_final', 'consulta_assincrona_inicio'])]
        
        estatisticas["analise_tipo_consulta"] = {
            "consultas_ano_unico": {
                "total": convert_numpy_types(len(consultas_unicas)),
                "tempo_medio": convert_numpy_types(consultas_unicas['tempo_total_segundos'].mean()),
                "registros_medio": convert_numpy_types(consultas_unicas['numero_registros'].mean())
            },
            "consultas_multiplos_anos": {
                "total": convert_numpy_types(len(consultas_multiplas)),
                "tempo_medio": convert_numpy_types(consultas_multiplas['tempo_total_segundos'].mean()),
                "registros_medio": convert_numpy_types(consultas_multiplas['numero_registros'].mean())
            }
        }
        
        # Converte DataFrame para lista de dicionários e trata tipos numpy
        metricas = df.to_dict('records')
        
        # Converte tipos numpy para tipos Python nativos
        for metrica in metricas:
            for key, value in metrica.items():
                metrica[key] = convert_numpy_types(value)
        
        return {
            "estatisticas": estatisticas,
            "metricas": metricas,
            "organizacao": "por_ano",
            "gerado_em": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter métricas de performance: {e}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": f"Erro ao processar métricas: {str(e)}"}

@router.get("/performance-summary", 
           summary="Obtém resumo estatístico das métricas de performance organizadas por ano")
async def obter_resumo_performance(response: Response):
    """
    Retorna apenas um resumo estatístico das métricas para sistema organizado por ano.
    Útil para dashboards e monitoramento.
    """
    try:
        csv_path = performance_tracker.csv_path
        
        if not os.path.exists(csv_path):
            response.status_code = status.HTTP_404_NOT_FOUND
            return {"error": "Arquivo de métricas não encontrado"}
        
        df = pd.read_csv(csv_path)
        
        if df.empty:
            return {"total_consultas": 0, "organizacao": "por_ano"}
        
        # Filtra apenas consultas concluídas (organizadas por ano)
        df_concluidas = df[df['operation'].isin(['consulta_sincrona', 'consulta_assincrona_final'])]
        
        resumo = {
            "periodo_analise": {
                "data_inicio": str(df['timestamp'].min()),
                "data_fim": str(df['timestamp'].max())
            },
            "organizacao": "por_ano",
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
            "tipos_operacao": {str(k): convert_numpy_types(v) for k, v in df['operation'].value_counts().to_dict().items()},
            "eficiencia_por_ano": {}
        }
        
        # Análise de eficiência por ano processado
        if 'ano_inicio' in df_concluidas.columns and 'ano_fim' in df_concluidas.columns:
            # Consultas de ano único vs múltiplos anos
            consultas_unico = df_concluidas[df_concluidas['ano_inicio'] == df_concluidas['ano_fim']]
            consultas_multiplos = df_concluidas[df_concluidas['ano_inicio'] != df_concluidas['ano_fim']]
            
            if len(consultas_unico) > 0:
                resumo["eficiencia_por_ano"]["consultas_ano_unico"] = {
                    "quantidade": convert_numpy_types(len(consultas_unico)),
                    "tempo_medio": round(convert_numpy_types(consultas_unico['tempo_total_segundos'].mean()), 2),
                    "registros_medio": round(convert_numpy_types(consultas_unico['numero_registros'].mean()), 2)
                }
            
            if len(consultas_multiplos) > 0:
                resumo["eficiencia_por_ano"]["consultas_multiplos_anos"] = {
                    "quantidade": convert_numpy_types(len(consultas_multiplos)),
                    "tempo_medio": round(convert_numpy_types(consultas_multiplos['tempo_total_segundos'].mean()), 2),
                    "registros_medio": round(convert_numpy_types(consultas_multiplos['numero_registros'].mean()), 2)
                }
        
        return resumo
        
    except Exception as e:
        logger.error(f"Erro ao obter resumo de performance: {e}")
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": f"Erro ao processar resumo: {str(e)}"}

@router.post("/cancelar-consulta/{id_consulta}")
async def cancelar_consulta(id_consulta: str):
    """
    Cancela uma consulta em andamento.
    
    Args:
        id_consulta: ID da consulta a ser cancelada
        
    Returns:
        Status da operação de cancelamento
    """
    try:
        # Verificar se a consulta existe
        consulta = consulta_service.consulta_repo.obter_consulta(id_consulta)
        
        if "error" in consulta:
            raise HTTPException(status_code=404, detail="Consulta não encontrada")
        
        # Verificar se a consulta já foi concluída
        if consulta["status"] in ["concluido", "erro"]:
            return {
                "status": "erro", 
                "mensagem": f"Consulta já está no estado '{consulta['status']}', não pode ser cancelada"
            }
        
        # Solicitar cancelamento
        resultado = consulta_service.cancelar_consulta(id_consulta)
        
        return {
            "status": "cancelamento_solicitado",
            "mensagem": "A consulta será cancelada assim que possível",
            "id_consulta": id_consulta
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erro ao cancelar consulta {id_consulta}: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/chrome-info")
async def chrome_info():
    """Retorna informações sobre Chrome e ChromeDriver instalados."""
    import subprocess
    import os
    
    info = {
        "chrome_installed": False,
        "chrome_version": None,
        "chrome_path": None,
        "chromedriver_installed": False,
        "chromedriver_version": None,
        "chromedriver_path": None,
        "selenium_version": None
    }
    
    # Verificar Chrome
    chrome_bin = os.getenv('CHROME_BIN', '/usr/bin/google-chrome')
    if os.path.exists(chrome_bin):
        info["chrome_installed"] = True
        info["chrome_path"] = chrome_bin
        try:
            result = subprocess.run([chrome_bin, '--version'], capture_output=True, text=True)
            info["chrome_version"] = result.stdout.strip()
        except:
            pass
    
    # Verificar ChromeDriver
    chromedriver_bin = os.getenv('CHROMEDRIVER_BIN', '/usr/local/bin/chromedriver')
    if os.path.exists(chromedriver_bin):
        info["chromedriver_installed"] = True
        info["chromedriver_path"] = chromedriver_bin
        try:
            result = subprocess.run([chromedriver_bin, '--version'], capture_output=True, text=True)
            info["chromedriver_version"] = result.stdout.strip()
        except:
            pass
    
    # Versão do Selenium
    try:
        import selenium
        info["selenium_version"] = selenium.__version__
    except:
        pass
    
    return info