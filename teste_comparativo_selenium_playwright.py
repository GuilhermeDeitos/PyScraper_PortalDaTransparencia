"""
Script de exemplo para demonstrar e testar o sistema de métricas de performance do Playwright.
Este script compara Selenium vs Playwright e gera dados de exemplo no CSV de métricas.
"""
import requests
import time
import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Any, List

# Configurações da API
API_BASE_URL = "http://localhost:8000"
ENDPOINTS = {
    "selenium": {
        "consultar": f"{API_BASE_URL}/consultar",
        "status": f"{API_BASE_URL}/status-consulta"
    },
    "playwright": {
        "consultar": f"{API_BASE_URL}/consultar-playwright",
        "status": f"{API_BASE_URL}/status-consulta-playwright"
    },
    "metrics": f"{API_BASE_URL}/performance-metrics",
    "summary": f"{API_BASE_URL}/performance-summary"
}

def fazer_consulta_selenium(ano: int, mes_inicio: str, mes_fim: str) -> Dict[str, Any]:
    """
    Faz uma consulta usando Selenium.
    
    Args:
        ano: Ano para consulta
        mes_inicio: Mês inicial (formato: "01")
        mes_fim: Mês final (formato: "12")
        
    Returns:
        Dicionário com resultado da consulta
    """
    payload = {
        "data_inicio": f"{mes_inicio}/{ano}",
        "data_fim": f"{mes_fim}/{ano}"
    }
    
    print(f"Selenium - Consultando {ano}, {mes_inicio} a {mes_fim}...")
    start_time = time.time()
    
    try:
        response = requests.post(ENDPOINTS["selenium"]["consultar"], json=payload, timeout=300)
        end_time = time.time()
        duration = end_time - start_time
        
        resultado = {
            "engine": "Selenium",
            "status_code": response.status_code,
            "tempo_segundos": duration,
            "sucesso": response.status_code == 200,
            "registros": 0,
            "erro": None
        }
        
        if response.status_code == 200:
            data = response.json()
            resultado["registros"] = data.get('total_registros', 0)
            print(f"Selenium SUCCESS - {resultado['registros']} registros em {duration:.2f}s")
        else:
            resultado["erro"] = response.text
            print(f"Selenium ERROR {response.status_code}: {response.text}")
            
        return resultado
        
    except requests.exceptions.Timeout:
        print("Selenium TIMEOUT na requisição")
        return {
            "engine": "Selenium",
            "status_code": 408,
            "tempo_segundos": 300,
            "sucesso": False,
            "registros": 0,
            "erro": "Timeout"
        }
    except Exception as e:
        print(f"Selenium EXCEPTION: {e}")
        return {
            "engine": "Selenium",
            "status_code": 500,
            "tempo_segundos": 0,
            "sucesso": False,
            "registros": 0,
            "erro": str(e)
        }

def fazer_consulta_playwright(ano: int, mes_inicio: str, mes_fim: str) -> Dict[str, Any]:
    """
    Faz uma consulta usando Playwright.
    
    Args:
        ano: Ano para consulta
        mes_inicio: Mês inicial (formato: "01")
        mes_fim: Mês final (formato: "12")
        
    Returns:
        Dicionário com resultado da consulta
    """
    payload = {
        "data_inicio": f"{mes_inicio}/{ano}",
        "data_fim": f"{mes_fim}/{ano}"
    }
    
    print(f"Playwright - Consultando {ano}, {mes_inicio} a {mes_fim}...")
    start_time = time.time()
    
    try:
        response = requests.post(ENDPOINTS["playwright"]["consultar"], json=payload, timeout=300)
        end_time = time.time()
        duration = end_time - start_time
        
        resultado = {
            "engine": "Playwright",
            "status_code": response.status_code,
            "tempo_segundos": duration,
            "sucesso": response.status_code == 200,
            "registros": 0,
            "erro": None
        }
        
        if response.status_code == 200:
            data = response.json()
            resultado["registros"] = data.get('total_registros', 0)
            print(f"Playwright SUCCESS - {resultado['registros']} registros em {duration:.2f}s")
        else:
            resultado["erro"] = response.text
            print(f"Playwright ERROR {response.status_code}: {response.text}")
            
        return resultado
        
    except requests.exceptions.Timeout:
        print("Playwright TIMEOUT na requisição")
        return {
            "engine": "Playwright",
            "status_code": 408,
            "tempo_segundos": 300,
            "sucesso": False,
            "registros": 0,
            "erro": "Timeout"
        }
    except Exception as e:
        print(f"Playwright EXCEPTION: {e}")
        return {
            "engine": "Playwright",
            "status_code": 500,
            "tempo_segundos": 0,
            "sucesso": False,
            "registros": 0,
            "erro": str(e)
        }

def fazer_teste_comparativo(ano: int, mes_inicio: str = "01", mes_fim: str = "12") -> Dict[str, Any]:
    """
    Faz um teste comparativo entre Selenium e Playwright.
    
    Args:
        ano: Ano para teste
        mes_inicio: Mês inicial
        mes_fim: Mês final
        
    Returns:
        Dicionário com resultados comparativos
    """
    print(f"\nTESTE COMPARATIVO - {ano} ({mes_inicio}/{mes_fim})")
    print("=" * 60)
    
    # Teste Selenium
    resultado_selenium = fazer_consulta_selenium(ano, mes_inicio, mes_fim)
    
    # Pausa entre testes
    print("Aguardando 5 segundos entre testes...")
    time.sleep(5)
    
    # Teste Playwright
    resultado_playwright = fazer_consulta_playwright(ano, mes_inicio, mes_fim)
    
    # Análise comparativa
    if resultado_selenium["sucesso"] and resultado_playwright["sucesso"]:
        diferenca_tempo = resultado_playwright["tempo_segundos"] - resultado_selenium["tempo_segundos"]
        diferenca_registros = resultado_playwright["registros"] - resultado_selenium["registros"]
        percentual_tempo = (diferenca_tempo / resultado_selenium["tempo_segundos"]) * 100
        
        print(f"\nCOMPARACAO DETALHADA:")
        print(f"   Tempo: Selenium {resultado_selenium['tempo_segundos']:.2f}s vs Playwright {resultado_playwright['tempo_segundos']:.2f}s")
        print(f"   Diferenca: {diferenca_tempo:+.2f}s ({percentual_tempo:+.1f}%)")
        print(f"   Vencedor tempo: {'Selenium' if diferenca_tempo > 0 else 'Playwright'}")
        print(f"   Registros: Selenium {resultado_selenium['registros']} vs Playwright {resultado_playwright['registros']}")
        print(f"   Diferenca registros: {diferenca_registros:+}")
        
        if abs(diferenca_registros) > 0:
            print(f"   ATENCAO: Diferenca nos registros detectada!")
            if diferenca_registros > 0:
                print(f"   Playwright retornou {diferenca_registros} registros a mais")
            else:
                print(f"   Selenium retornou {abs(diferenca_registros)} registros a mais")
    elif not resultado_selenium["sucesso"] and not resultado_playwright["sucesso"]:
        print(f"\nAMBOS OS TESTES FALHARAM:")
        print(f"   Selenium: {resultado_selenium['erro']}")
        print(f"   Playwright: {resultado_playwright['erro']}")
    elif not resultado_selenium["sucesso"]:
        print(f"\nAPENAS PLAYWRIGHT FUNCIONOU:")
        print(f"   Playwright: {resultado_playwright['registros']} registros em {resultado_playwright['tempo_segundos']:.2f}s")
        print(f"   Selenium falhou: {resultado_selenium['erro']}")
    else:
        print(f"\nAPENAS SELENIUM FUNCIONOU:")
        print(f"   Selenium: {resultado_selenium['registros']} registros em {resultado_selenium['tempo_segundos']:.2f}s")
        print(f"   Playwright falhou: {resultado_playwright['erro']}")
    
    return {
        "ano": ano,
        "periodo": f"{mes_inicio}/{mes_fim}",
        "selenium": resultado_selenium,
        "playwright": resultado_playwright,
        "timestamp": datetime.now().isoformat()
    }

async def fazer_consulta_playwright_assincrona(ano_inicio: int, ano_fim: int, mes_inicio: str = "01", mes_fim: str = "12") -> Dict[str, Any]:
    """
    Faz uma consulta assíncrona usando Playwright.
    
    Args:
        ano_inicio: Ano inicial
        ano_fim: Ano final
        mes_inicio: Mês inicial
        mes_fim: Mês final
        
    Returns:
        Dicionário com resultado da consulta
    """
    payload = {
        "data_inicio": f"{mes_inicio}/{ano_inicio}",
        "data_fim": f"{mes_fim}/{ano_fim}"
    }
    
    print(f"Playwright Assincrono - {ano_inicio} a {ano_fim}...")
    start_time = time.time()
    
    try:
        async with aiohttp.ClientSession() as session:
            # Inicia a consulta
            async with session.post(ENDPOINTS["playwright"]["consultar"], json=payload) as response:
                if response.status == 202:
                    data = await response.json()
                    id_consulta = data.get("id_consulta")
                    print(f"Playwright - Consulta iniciada com ID: {id_consulta}")
                    
                    # Monitora o progresso
                    timeout_contador = 0
                    max_timeout = 120  # 10 minutos (120 * 5 segundos)
                    
                    while timeout_contador < max_timeout:
                        async with session.get(f"{ENDPOINTS['playwright']['status']}/{id_consulta}") as status_response:
                            status_data = await status_response.json()
                            status_atual = status_data.get('status', 'unknown')
                            
                            print(f"Status: {status_atual} (verificacao {timeout_contador + 1})")
                            
                            if status_atual == "concluido":
                                end_time = time.time()
                                duration = end_time - start_time
                                registros = status_data.get('total_registros', 0)
                                print(f"Playwright Async SUCCESS - {registros} registros em {duration:.2f}s")
                                
                                return {
                                    "engine": "Playwright-Async",
                                    "anos": f"{ano_inicio}-{ano_fim}",
                                    "tempo_segundos": duration,
                                    "sucesso": True,
                                    "registros": registros,
                                    "erro": None
                                }
                            elif status_atual == "erro":
                                erro = status_data.get('erro', 'Erro desconhecido')
                                print(f"Playwright Async ERROR: {erro}")
                                return {
                                    "engine": "Playwright-Async",
                                    "anos": f"{ano_inicio}-{ano_fim}",
                                    "tempo_segundos": time.time() - start_time,
                                    "sucesso": False,
                                    "registros": 0,
                                    "erro": erro
                                }
                            
                            timeout_contador += 1
                            await asyncio.sleep(5)  # Aguarda 5 segundos
                    
                    # Timeout atingido
                    print(f"Playwright Async TIMEOUT após {max_timeout * 5} segundos")
                    return {
                        "engine": "Playwright-Async",
                        "anos": f"{ano_inicio}-{ano_fim}",
                        "tempo_segundos": time.time() - start_time,
                        "sucesso": False,
                        "registros": 0,
                        "erro": "Timeout aguardando conclusão"
                    }
                else:
                    error_text = await response.text()
                    print(f"Playwright Async ERROR {response.status}: {error_text}")
                    return {
                        "engine": "Playwright-Async",
                        "anos": f"{ano_inicio}-{ano_fim}",
                        "tempo_segundos": 0,
                        "sucesso": False,
                        "registros": 0,
                        "erro": error_text
                    }
                    
    except Exception as e:
        print(f"Playwright Async EXCEPTION: {e}")
        return {
            "engine": "Playwright-Async",
            "anos": f"{ano_inicio}-{ano_fim}",
            "tempo_segundos": 0,
            "sucesso": False,
            "registros": 0,
            "erro": str(e)
        }

def executar_bateria_testes_sincronos():
    """Executa uma bateria de testes síncronos comparativos."""
    print("\nBATERIA DE TESTES SINCRONOS")
    print("=" * 60)
    
    testes = [
        {"ano": 2023, "mes_inicio": "01", "mes_fim": "03"},  # Trimestre
        {"ano": 2022, "mes_inicio": "01", "mes_fim": "06"},  # Semestre
        {"ano": 2021, "mes_inicio": "01", "mes_fim": "12"},  # Ano completo
        {"ano": 2020, "mes_inicio": "07", "mes_fim": "12"},  # Segundo semestre
    ]
    
    resultados = []
    
    for i, teste in enumerate(testes, 1):
        print(f"\n--- Teste Sincrono {i}/{len(testes)} ---")
        resultado = fazer_teste_comparativo(**teste)
        resultados.append(resultado)
        
        # Pausa entre testes
        if i < len(testes):
            print("Aguardando 10 segundos antes do próximo teste...")
            time.sleep(10)
    
    return resultados

async def executar_testes_assincronos():
    """Executa testes assíncronos com Playwright."""
    print("\nTESTES ASSINCRONOS PLAYWRIGHT")
    print("=" * 60)
    
    testes_async = [
        {"ano_inicio": 2020, "ano_fim": 2023},     # 4 anos
        {"ano_inicio": 2018, "ano_fim": 2021},     # 4 anos
        {"ano_inicio": 2015, "ano_fim": 2017},     # 3 anos
    ]
    
    resultados = []
    
    for i, teste in enumerate(testes_async, 1):
        print(f"\n--- Teste Assincrono {i}/{len(testes_async)} ---")
        resultado = await fazer_consulta_playwright_assincrona(**teste)
        resultados.append(resultado)
        
        # Pausa entre testes
        if i < len(testes_async):
            print("Aguardando 15 segundos antes do próximo teste...")
            await asyncio.sleep(15)
    
    return resultados

def visualizar_metricas_comparativas():
    """Visualiza métricas comparativas entre Selenium e Playwright."""
    try:
        print("\nRESUMO DE PERFORMANCE COMPARATIVO")
        print("=" * 60)
        
        response = requests.get(ENDPOINTS["summary"])
        
        if response.status_code == 200:
            summary = response.json()
            
            periodo = summary.get('periodo_analise', {})
            print(f"Periodo analisado: {periodo.get('data_inicio', 'N/A')} a {periodo.get('data_fim', 'N/A')}")
            
            consultas = summary.get('consultas', {})
            performance = summary.get('performance', {})
            dados = summary.get('dados', {})
            
            print(f"\nESTATISTICAS GERAIS:")
            print(f"   Total de consultas: {consultas.get('total', 0)}")
            print(f"   Bem-sucedidas: {consultas.get('bem_sucedidas', 0)}")
            print(f"   Com erro: {consultas.get('com_erro', 0)}")
            print(f"   Taxa de sucesso: {consultas.get('taxa_sucesso_percentual', 0):.1f}%")
            
            print(f"\nPERFORMANCE:")
            print(f"   Tempo médio: {performance.get('tempo_medio_segundos', 0):.2f}s")
            print(f"   Tempo mediano: {performance.get('tempo_mediano_segundos', 0):.2f}s")
            print(f"   Tempo mínimo: {performance.get('tempo_minimo_segundos', 0):.2f}s")
            print(f"   Tempo máximo: {performance.get('tempo_maximo_segundos', 0):.2f}s")
            
            print(f"\nDADOS:")
            print(f"   Total de registros: {dados.get('total_registros_processados', 0):,}")
            print(f"   Média por consulta: {dados.get('media_registros_por_consulta', 0):.1f}")
            print(f"   Throughput: {dados.get('registros_por_segundo_medio', 0):.2f} registros/s")
            
        else:
            print(f"ERRO ao obter resumo: {response.status_code}")
            
    except Exception as e:
        print(f"ERRO ao visualizar métricas: {e}")

def calcular_estatisticas_detalhadas(resultados_sincronos: List[Dict], resultados_assincronos: List[Dict]):
    """Calcula estatísticas detalhadas dos testes."""
    print("\nESTATISTICAS DETALHADAS")
    print("=" * 60)
    
    # Análise dos testes síncronos
    selenium_sucessos = []
    playwright_sucessos = []
    selenium_registros = []
    playwright_registros = []
    
    for resultado in resultados_sincronos:
        if resultado["selenium"]["sucesso"]:
            selenium_sucessos.append(resultado["selenium"]["tempo_segundos"])
            selenium_registros.append(resultado["selenium"]["registros"])
        if resultado["playwright"]["sucesso"]:
            playwright_sucessos.append(resultado["playwright"]["tempo_segundos"])
            playwright_registros.append(resultado["playwright"]["registros"])
    
    print("TESTES SINCRONOS:")
    if selenium_sucessos:
        avg_selenium = sum(selenium_sucessos) / len(selenium_sucessos)
        min_selenium = min(selenium_sucessos)
        max_selenium = max(selenium_sucessos)
        print(f"   Selenium - Sucessos: {len(selenium_sucessos)}")
        print(f"   Selenium - Tempo médio: {avg_selenium:.2f}s (min: {min_selenium:.2f}s, max: {max_selenium:.2f}s)")
        print(f"   Selenium - Registros médios: {sum(selenium_registros) / len(selenium_registros):.0f}")
    
    if playwright_sucessos:
        avg_playwright = sum(playwright_sucessos) / len(playwright_sucessos)
        min_playwright = min(playwright_sucessos)
        max_playwright = max(playwright_sucessos)
        print(f"   Playwright - Sucessos: {len(playwright_sucessos)}")
        print(f"   Playwright - Tempo médio: {avg_playwright:.2f}s (min: {min_playwright:.2f}s, max: {max_playwright:.2f}s)")
        print(f"   Playwright - Registros médios: {sum(playwright_registros) / len(playwright_registros):.0f}")
    
    if selenium_sucessos and playwright_sucessos:
        diferenca_percentual = ((avg_playwright - avg_selenium) / avg_selenium) * 100
        print(f"   Diferença média: {diferenca_percentual:+.1f}% (Playwright vs Selenium)")
        if diferenca_percentual < 0:
            print(f"   RESULTADO: Playwright é {abs(diferenca_percentual):.1f}% mais rápido")
        else:
            print(f"   RESULTADO: Selenium é {diferenca_percentual:.1f}% mais rápido")
    
    # Análise dos testes assíncronos
    print(f"\nTESTES ASSINCRONOS:")
    async_sucessos = [r for r in resultados_assincronos if r["sucesso"]]
    async_falhas = [r for r in resultados_assincronos if not r["sucesso"]]
    
    print(f"   Total de testes: {len(resultados_assincronos)}")
    print(f"   Sucessos: {len(async_sucessos)}")
    print(f"   Falhas: {len(async_falhas)}")
    
    if async_sucessos:
        tempos_async = [r["tempo_segundos"] for r in async_sucessos]
        registros_async = [r["registros"] for r in async_sucessos]
        print(f"   Tempo médio: {sum(tempos_async) / len(tempos_async):.2f}s")
        print(f"   Registros médios: {sum(registros_async) / len(registros_async):.0f}")
    
    if async_falhas:
        print(f"   Principais erros:")
        erros_contados = {}
        for falha in async_falhas:
            erro = falha.get("erro", "Erro desconhecido")
            erros_contados[erro] = erros_contados.get(erro, 0) + 1
        for erro, count in erros_contados.items():
            print(f"     - {erro}: {count} vezes")

def gerar_relatorio_final(resultados_sincronos: List[Dict], resultados_assincronos: List[Dict]):
    """Gera um relatório final com recomendações."""
    print("\nRELATORIO FINAL E RECOMENDACOES")
    print("=" * 80)
    
    # Análise de confiabilidade
    total_sincronos = len(resultados_sincronos) * 2  # Selenium + Playwright
    sucessos_selenium = sum(1 for r in resultados_sincronos if r["selenium"]["sucesso"])
    sucessos_playwright = sum(1 for r in resultados_sincronos if r["playwright"]["sucesso"])
    
    print("CONFIABILIDADE:")
    print(f"   Selenium: {sucessos_selenium}/{len(resultados_sincronos)} ({(sucessos_selenium/len(resultados_sincronos)*100):.1f}% sucesso)")
    print(f"   Playwright: {sucessos_playwright}/{len(resultados_sincronos)} ({(sucessos_playwright/len(resultados_sincronos)*100):.1f}% sucesso)")
    
    # Análise de performance
    selenium_tempos = [r["selenium"]["tempo_segundos"] for r in resultados_sincronos if r["selenium"]["sucesso"]]
    playwright_tempos = [r["playwright"]["tempo_segundos"] for r in resultados_sincronos if r["playwright"]["sucesso"]]
    
    print("\nPERFORMANCE:")
    if selenium_tempos and playwright_tempos:
        avg_selenium = sum(selenium_tempos) / len(selenium_tempos)
        avg_playwright = sum(playwright_tempos) / len(playwright_tempos)
        
        if avg_playwright < avg_selenium:
            vencedor = "Playwright"
            diferenca = ((avg_selenium - avg_playwright) / avg_selenium) * 100
        else:
            vencedor = "Selenium"
            diferenca = ((avg_playwright - avg_selenium) / avg_playwright) * 100
        
        print(f"   Vencedor em velocidade: {vencedor} ({diferenca:.1f}% mais rápido)")
    
    # Análise de dados
    diferenca_registros = []
    for resultado in resultados_sincronos:
        if resultado["selenium"]["sucesso"] and resultado["playwright"]["sucesso"]:
            diff = resultado["playwright"]["registros"] - resultado["selenium"]["registros"]
            diferenca_registros.append(diff)
    
    if diferenca_registros:
        avg_diff = sum(diferenca_registros) / len(diferenca_registros)
        print(f"\nDADOS:")
        print(f"   Diferença média de registros: {avg_diff:+.1f}")
        if abs(avg_diff) > 10:
            print(f"   ALERTA: Diferença significativa nos dados entre engines!")
    
    # Recomendações
    print(f"\nRECOMENDACOES:")
    
    if sucessos_selenium > sucessos_playwright:
        print("   1. Selenium apresenta maior confiabilidade")
    elif sucessos_playwright > sucessos_selenium:
        print("   1. Playwright apresenta maior confiabilidade")
    else:
        print("   1. Ambas engines têm confiabilidade similar")
    
    if selenium_tempos and playwright_tempos:
        if avg_playwright < avg_selenium:
            print("   2. Usar Playwright para performance (consultas síncronas)")
        else:
            print("   2. Usar Selenium para performance (consultas síncronas)")
    
    print("   3. Playwright recomendado para consultas assíncronas (suporte nativo)")
    print("   4. Investigar diferenças nos dados se persistirem")
    print("   5. Monitorar métricas continuamente")

async def main():
    """Função principal do script de teste."""
    print("ANALISE COMPARATIVA: SELENIUM vs PLAYWRIGHT")
    print("=" * 80)
    print(f"Iniciado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    try:
        # Executa testes síncronos
        print("\nFase 1: Executando testes síncronos...")
        resultados_sincronos = executar_bateria_testes_sincronos()
        
        # Pausa entre fases
        print("\nAguardando 30 segundos antes dos testes assíncronos...")
        await asyncio.sleep(30)
        
        # Executa testes assíncronos
        print("\nFase 2: Executando testes assíncronos...")
        resultados_assincronos = await executar_testes_assincronos()
        
        # Análises finais
        print("\nFase 3: Analisando resultados...")
        visualizar_metricas_comparativas()
        calcular_estatisticas_detalhadas(resultados_sincronos, resultados_assincronos)
        gerar_relatorio_final(resultados_sincronos, resultados_assincronos)
        
    except KeyboardInterrupt:
        print("\nTeste interrompido pelo usuário")
    except Exception as e:
        print(f"\nERRO durante execução: {e}")
    
    print(f"\nANALISE CONCLUIDA!")
    print(f"Timestamp final: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Métricas salvas em 'performance_metrics.csv'")
    print(f"Endpoints disponíveis:")
    print(f"   - Métricas: GET {ENDPOINTS['metrics']}")
    print(f"   - Resumo: GET {ENDPOINTS['summary']}")

if __name__ == "__main__":
    asyncio.run(main())