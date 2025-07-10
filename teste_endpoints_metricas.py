#!/usr/bin/env python3
"""
Script para testar os endpoints de métricas após correção de serialização.
Verifica se os endpoints retornam JSON válido e se todos os tipos são serializáveis.
"""

import requests
import json
import sys
import traceback
from datetime import datetime

BASE_URL = "http://localhost:8000"

def test_json_serializable(data, endpoint_name):
    """
    Testa se os dados são serializáveis para JSON
    """
    try:
        json_str = json.dumps(data)
        print(f"✅ {endpoint_name}: JSON serialization successful")
        return True
    except Exception as e:
        print(f"❌ {endpoint_name}: JSON serialization failed - {e}")
        return False

def test_endpoint(endpoint, endpoint_name):
    """
    Testa um endpoint específico
    """
    print(f"\n🔍 Testando endpoint: {endpoint_name}")
    print(f"URL: {BASE_URL}{endpoint}")
    
    try:
        response = requests.get(f"{BASE_URL}{endpoint}")
        print(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"Resposta recebida com sucesso")
            
            # Verifica se é serializável para JSON
            if test_json_serializable(data, endpoint_name):
                # Mostra um resumo dos dados
                if isinstance(data, dict):
                    print(f"Chaves principais: {list(data.keys())}")
                    
                    if "estatisticas" in data:
                        print(f"Total consultas: {data['estatisticas'].get('total_consultas', 'N/A')}")
                    if "consultas" in data:
                        print(f"Total consultas: {data['consultas'].get('total', 'N/A')}")
                    if "metricas" in data:
                        print(f"Número de métricas: {len(data['metricas'])}")
                
                return True
            else:
                return False
        else:
            print(f"❌ Erro HTTP: {response.status_code}")
            try:
                error_data = response.json()
                print(f"Detalhes do erro: {error_data}")
            except:
                print(f"Resposta não é JSON válido: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print(f"❌ Erro de conexão. Certifique-se de que o servidor está rodando em {BASE_URL}")
        return False
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        traceback.print_exc()
        return False

def test_consulta_endpoint():
    """
    Faz uma consulta rápida para gerar algumas métricas se necessário
    """
    print(f"\n🔍 Testando endpoint de consulta para gerar métricas")
    
    try:
        consulta_data = {
            "ano_inicio": 2024,
            "mes_inicio": 1,
            "ano_fim": 2024,
            "mes_fim": 2,
            "codigo_orgao": "20000",
            "assincrono": False
        }
        
        response = requests.post(f"{BASE_URL}/consultar", json=consulta_data)
        print(f"Status Code da consulta: {response.status_code}")
        
        if response.status_code in [200, 202]:
            print("✅ Consulta realizada com sucesso (pode ter dados ou não)")
            return True
        else:
            print(f"❌ Consulta falhou: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Erro na consulta: {e}")
        return False

def main():
    print("=" * 60)
    print("🧪 TESTE DOS ENDPOINTS DE MÉTRICAS")
    print("=" * 60)
    print(f"Executando em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Lista de endpoints para testar
    endpoints = [
        ("/performance-metrics", "Performance Metrics"),
        ("/performance-summary", "Performance Summary")
    ]
    
    results = []
    
    # Testa cada endpoint
    for endpoint, name in endpoints:
        success = test_endpoint(endpoint, name)
        results.append((name, success))
    
    # Se não há métricas, tenta fazer uma consulta
    if not any(result[1] for result in results):
        print("\n⚠️  Parece que não há métricas disponíveis.")
        print("Tentando fazer uma consulta para gerar métricas...")
        
        if test_consulta_endpoint():
            print("\n🔄 Testando endpoints novamente após consulta...")
            for endpoint, name in endpoints:
                success = test_endpoint(endpoint, name)
                # Atualiza resultado
                for i, (result_name, _) in enumerate(results):
                    if result_name == name:
                        results[i] = (result_name, success)
                        break
    
    # Resumo final
    print("\n" + "=" * 60)
    print("📊 RESUMO DOS TESTES")
    print("=" * 60)
    
    all_passed = True
    for name, success in results:
        status = "✅ PASSOU" if success else "❌ FALHOU"
        print(f"{name}: {status}")
        if not success:
            all_passed = False
    
    if all_passed:
        print("\n🎉 Todos os testes passaram! Os endpoints estão funcionando corretamente.")
        sys.exit(0)
    else:
        print("\n⚠️  Alguns testes falharam. Verifique os erros acima.")
        sys.exit(1)

if __name__ == "__main__":
    main()
