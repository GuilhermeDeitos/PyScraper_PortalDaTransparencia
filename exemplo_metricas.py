"""
Script de exemplo para demonstrar o uso do sistema de métricas de performance.
Este script pode ser usado para testar a API e gerar dados de exemplo no CSV de métricas.
"""
import requests
import time
import json
from datetime import datetime

# Configurações da API
API_BASE_URL = "http://localhost:8000"  # Ajuste conforme necessário
ENDPOINTS = {
    "consultar": f"{API_BASE_URL}/consultar",
    "status": f"{API_BASE_URL}/status-consulta",
    "metrics": f"{API_BASE_URL}/performance-metrics",
    "summary": f"{API_BASE_URL}/performance-summary"
}

def fazer_consulta_sincrona(ano: int, mes_inicio: str, mes_fim: str):
    """
    Faz uma consulta síncrona (mesmo ano para início e fim).
    
    Args:
        ano: Ano para consulta
        mes_inicio: Mês inicial (formato: "2023-01-01")
        mes_fim: Mês final (formato: "2023-12-31")
    """
    payload = {
        "data_inicio": f"{mes_inicio}/{ano}",
        "data_fim": f"{mes_fim}/{ano}"
    }
    
    print(f"Fazendo consulta síncrona para {ano}, {mes_inicio} a {mes_fim}...")
    start_time = time.time()
    
    try:
        response = requests.post(ENDPOINTS["consultar"], json=payload, timeout=300)
        end_time = time.time()
        
        print(f"Status: {response.status_code}")
        print(f"Tempo de resposta: {end_time - start_time:.2f} segundos")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Registros obtidos: {data.get('total_registros', 0)}")
        else:
            print(f"Erro: {response.text}")
            
    except requests.exceptions.Timeout:
        print("Timeout na requisição")
    except Exception as e:
        print(f"Erro: {e}")

def fazer_consulta_assincrona(ano_inicio: int, ano_fim: int, mes_inicio: str = "01", mes_fim: str = "12"):
    """
    Faz uma consulta assíncrona (múltiplos anos).
    
    Args:
        ano_inicio: Ano inicial
        ano_fim: Ano final
        mes_inicio: Mês inicial (formato: "01")
        mes_fim: Mês final (formato: "12")
    """
    payload = {
        "data_inicio": f"{mes_inicio}/{ano_inicio}",
        "data_fim": f"{mes_fim}/{ano_fim}"
    }
    
    print(f"Fazendo consulta assíncrona para {ano_inicio} a {ano_fim}...")
    
    try:
        # Inicia a consulta
        response = requests.post(ENDPOINTS["consultar"], json=payload, timeout=30)
        
        if response.status_code == 202:
            data = response.json()
            print(data)
            id_consulta = data.get("id_consulta")
            print(f"Consulta iniciada com ID: {id_consulta}")
            
            # Monitora o progresso
            while True:
                status_response = requests.get(f"{ENDPOINTS['status']}/{id_consulta}")
                status_data = status_response.json()
                
                print(f"Status atual: {status_data.get('status', 'unknown')}")
                
                if status_data.get("status") == "concluido":
                    print("Consulta concluída!")
                    print(f"Total de registros: {status_data.get('total_registros', 0)}")
                    break
                elif status_data.get("status") == "erro":
                    print(f"Erro na consulta: {status_data.get('erro', 'Erro desconhecido')}")
                    break
                
                time.sleep(10)  # Aguarda 10 segundos antes de verificar novamente
                
        else:
            print(f"Erro ao iniciar consulta: {response.status_code} - {response.text}")
            
    except Exception as e:
        print(f"Erro: {e}")

def visualizar_metricas():
    """Obtém e exibe as métricas de performance."""
    try:
        print("\\n=== RESUMO DE PERFORMANCE ===")
        response = requests.get(ENDPOINTS["summary"])
        
        if response.status_code == 200:
            summary = response.json()
            
            print(f"Período: {summary.get('periodo_analise', {}).get('data_inicio')} a {summary.get('periodo_analise', {}).get('data_fim')}")
            
            consultas = summary.get('consultas', {})
            print(f"\\nConsultas:")
            print(f"  Total: {consultas.get('total', 0)}")
            print(f"  Bem-sucedidas: {consultas.get('bem_sucedidas', 0)}")
            print(f"  Com erro: {consultas.get('com_erro', 0)}")
            print(f"  Taxa de sucesso: {consultas.get('taxa_sucesso_percentual', 0):.1f}%")
            
            performance = summary.get('performance', {})
            print(f"\\nPerformance:")
            print(f"  Tempo médio: {performance.get('tempo_medio_segundos', 0):.2f}s")
            print(f"  Tempo mediano: {performance.get('tempo_mediano_segundos', 0):.2f}s")
            print(f"  Tempo máximo: {performance.get('tempo_maximo_segundos', 0):.2f}s")
            print(f"  Tempo mínimo: {performance.get('tempo_minimo_segundos', 0):.2f}s")
            
            dados = summary.get('dados', {})
            print(f"\\nDados:")
            print(f"  Total de registros: {dados.get('total_registros_processados', 0)}")
            print(f"  Média por consulta: {dados.get('media_registros_por_consulta', 0):.1f}")
            print(f"  Registros/segundo: {dados.get('registros_por_segundo_medio', 0):.2f}")
            
        else:
            print(f"Erro ao obter resumo: {response.status_code}")
            
    except Exception as e:
        print(f"Erro ao visualizar métricas: {e}")

def main():
    """Função principal do script de exemplo."""
    print("=== TESTE DO SISTEMA DE MÉTRICAS DE PERFORMANCE ===\\n")
    
    # Exemplos de consultas para gerar métricas
    exemplos_consulta = [
        
        {"tipo": "assincrona", "ano_inicio": 2015, "ano_fim": 2023},
        {"tipo": "assincrona", "ano_inicio": 2015, "ano_fim": 2023},
        {"tipo": "assincrona", "ano_inicio": 2015, "ano_fim": 2023},
        {"tipo": "assincrona", "ano_inicio": 2015, "ano_fim": 2023},
        {"tipo": "assincrona", "ano_inicio": 2015, "ano_fim": 2023},

        {"tipo": "assincrona", "ano_inicio": 2003, "ano_fim": 2023, "mes_inicio": "07", "mes_fim": "12"},
        {"tipo": "assincrona", "ano_inicio": 2003, "ano_fim": 2023, "mes_inicio": "07", "mes_fim": "12"},
        {"tipo": "assincrona", "ano_inicio": 2003, "ano_fim": 2023, "mes_inicio": "07", "mes_fim": "12"},
        {"tipo": "assincrona", "ano_inicio": 2003, "ano_fim": 2023, "mes_inicio": "07", "mes_fim": "12"},
        {"tipo": "assincrona", "ano_inicio": 2003, "ano_fim": 2023, "mes_inicio": "07", "mes_fim": "12"},
        
        
        
        
        
        
        
    ]
    
    for i, exemplo in enumerate(exemplos_consulta, 1):
        print(f"\\n--- Teste {i} ---")
        
        if exemplo["tipo"] == "sincrona":
            fazer_consulta_sincrona(
                exemplo["ano"],
                exemplo["mes_inicio"],
                exemplo["mes_fim"]
            )
        elif exemplo["tipo"] == "assincrona":
            fazer_consulta_assincrona(
                exemplo["ano_inicio"],
                exemplo["ano_fim"]
            )
        
        # Pausa entre consultas
        time.sleep(2)
    
    # Visualiza as métricas geradas
    print("\\n" + "="*50)
    visualizar_metricas()
    
    print("\\n=== FINALIZADO ===")
    print("As métricas foram salvas no arquivo 'performance_metrics.csv'")
    print("Você pode acessar:")
    print(f"  - Resumo: GET {ENDPOINTS['summary']}")
    print(f"  - Métricas completas: GET {ENDPOINTS['metrics']}")

if __name__ == "__main__":
    main()
