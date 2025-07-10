"""
Script de teste simples para verificar se as métricas estão sendo calculadas corretamente.
"""
import requests
import time

# Configurações da API
API_BASE_URL = "http://localhost:8000"

def teste_consulta_simples():
    """Testa uma consulta simples e verifica se o tempo está sendo medido."""
    
    print("=== TESTE DE MEDIÇÃO DE TEMPO ===")
    
    # Consulta para um período pequeno (deve ser rápida)
    payload = {
        "data_inicio": "06/2022",
        "data_fim": "06/2022"
    }
    
    print(f"Fazendo consulta: {payload}")
    
    # Mede o tempo do lado do cliente
    inicio_cliente = time.time()
    
    try:
        response = requests.post(f"{API_BASE_URL}/consultar", json=payload, timeout=120)
        
        fim_cliente = time.time()
        tempo_cliente = fim_cliente - inicio_cliente
        
        print(f"Status: {response.status_code}")
        print(f"Tempo medido pelo cliente: {tempo_cliente:.2f} segundos")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Registros obtidos: {data.get('total_registros', 0)}")
        else:
            print(f"Erro: {response.text}")
        
        # Agora verifica as métricas na API
        print("\\nVerificando métricas na API...")
        
        time.sleep(1)  # Aguarda um pouco para garantir que a métrica foi salva
        
        metrics_response = requests.get(f"{API_BASE_URL}/performance-summary")
        
        if metrics_response.status_code == 200:
            metrics = metrics_response.json()
            
            print("\\n=== MÉTRICAS DA API ===")
            
            consultas = metrics.get('consultas', {})
            print(f"Total de consultas: {consultas.get('total', 0)}")
            print(f"Bem-sucedidas: {consultas.get('bem_sucedidas', 0)}")
            
            performance = metrics.get('performance', {})
            print(f"Tempo médio: {performance.get('tempo_medio_segundos', 0):.2f}s")
            print(f"Tempo máximo: {performance.get('tempo_maximo_segundos', 0):.2f}s")
            print(f"Tempo mínimo: {performance.get('tempo_minimo_segundos', 0):.2f}s")
            
            # Verifica se o tempo está sendo medido corretamente
            tempo_api = performance.get('tempo_medio_segundos', 0)
            if tempo_api > 0:
                print(f"\\n✅ SUCESSO: Tempo está sendo medido corretamente!")
                print(f"   Cliente: {tempo_cliente:.2f}s vs API: {tempo_api:.2f}s")
                
                diferenca = abs(tempo_cliente - tempo_api)
                if diferenca < 5:  # Tolerância de 5 segundos
                    print(f"   ✅ Tempos são consistentes (diferença: {diferenca:.2f}s)")
                else:
                    print(f"   ⚠️  Grande diferença entre tempos (diferença: {diferenca:.2f}s)")
            else:
                print(f"\\n❌ ERRO: Tempo não está sendo medido pela API!")
                print(f"   Cliente mediu {tempo_cliente:.2f}s, mas API registrou {tempo_api}s")
        else:
            print(f"Erro ao obter métricas: {metrics_response.status_code}")
            
    except Exception as e:
        print(f"Erro: {e}")

def listar_ultimas_metricas():
    """Lista as últimas métricas para análise."""
    try:
        print("\\n=== ÚLTIMAS MÉTRICAS ===")
        
        response = requests.get(f"{API_BASE_URL}/performance-metrics")
        
        if response.status_code == 200:
            data = response.json()
            metricas = data.get('metricas', [])
            
            if metricas:
                # Pega as últimas 5 métricas
                ultimas = metricas[-5:] if len(metricas) >= 5 else metricas
                
                print(f"Mostrando últimas {len(ultimas)} métricas:")
                
                for i, metrica in enumerate(ultimas, 1):
                    print(f"\\n{i}. {metrica.get('operation', 'N/A')}")
                    print(f"   Timestamp: {metrica.get('timestamp', 'N/A')}")
                    print(f"   Tempo total: {metrica.get('tempo_total_segundos', 0):.2f}s")
                    print(f"   Tempo scraping: {metrica.get('tempo_scraping_segundos', 0):.2f}s")
                    print(f"   Registros: {metrica.get('numero_registros', 0)}")
                    print(f"   Sucesso: {metrica.get('sucesso', False)}")
                    
                    if metrica.get('erro_descricao'):
                        print(f"   Erro: {metrica.get('erro_descricao')}")
            else:
                print("Nenhuma métrica encontrada.")
                
            # Mostra estatísticas resumidas também
            estatisticas = data.get('estatisticas', {})
            if estatisticas:
                print("\\n=== ESTATÍSTICAS RESUMIDAS ===")
                print(f"Total de consultas: {estatisticas.get('total_consultas', 0)}")
                print(f"Bem-sucedidas: {estatisticas.get('consultas_bem_sucedidas', 0)}")
                print(f"Com erro: {estatisticas.get('consultas_com_erro', 0)}")
                print(f"Tempo médio: {estatisticas.get('tempo_medio_segundos', 0):.2f}s")
                print(f"Total de registros: {estatisticas.get('total_registros_processados', 0)}")
                
        else:
            print(f"Erro ao obter métricas: {response.status_code}")
            print(f"Resposta: {response.text}")
            
    except Exception as e:
        print(f"Erro: {e}")

if __name__ == "__main__":
    teste_consulta_simples()
    listar_ultimas_metricas()
