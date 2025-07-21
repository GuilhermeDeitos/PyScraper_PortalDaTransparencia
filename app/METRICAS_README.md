# Sistema de Métricas de Performance

Este sistema foi implementado para rastrear e analisar o tempo de processamento das consultas da API do Portal da Transparência.

## Funcionalidades

### 1. Rastreamento Automático
- **Consultas Síncronas**: Mede tempo total e tempo de scraping
- **Consultas Assíncronas**: Mede tempo por ano e tempo total
- **Operações Detalhadas**: Tempo de inicialização do navegador, preenchimento de formulário, etc.

### 2. Armazenamento em CSV
As métricas são automaticamente salvas no arquivo `performance_metrics.csv` com as seguintes colunas:

| Coluna | Descrição |
|--------|-----------|
| `timestamp` | Data/hora da operação |
| `endpoint` | Endpoint da API usado |
| `operation` | Tipo de operação (consulta_sincrona, consulta_assincrona_ano, etc.) |
| `ano_inicio` | Ano inicial da consulta |
| `ano_fim` | Ano final da consulta |
| `mes_inicio` | Mês inicial |
| `mes_fim` | Mês final |
| `tempo_total_segundos` | Tempo total da operação |
| `tempo_scraping_segundos` | Tempo apenas do scraping |
| `tempo_processamento_segundos` | Tempo de processamento dos dados |
| `numero_registros` | Quantidade de registros retornados |
| `sucesso` | Se a operação foi bem-sucedida |
| `erro_descricao` | Descrição do erro (se houver) |
| `id_consulta` | ID da consulta (para operações assíncronas) |
| `thread_id` | ID da thread que executou |

### 3. Endpoints de Métricas

#### `/performance-summary`
Retorna um resumo estatístico das métricas:
```json
{
  "periodo_analise": {
    "data_inicio": "2025-01-01T10:00:00",
    "data_fim": "2025-01-02T15:30:00"
  },
  "consultas": {
    "total": 15,
    "bem_sucedidas": 14,
    "com_erro": 1,
    "taxa_sucesso_percentual": 93.3
  },
  "performance": {
    "tempo_medio_segundos": 45.2,
    "tempo_mediano_segundos": 42.1,
    "tempo_maximo_segundos": 78.5,
    "tempo_minimo_segundos": 28.3
  },
  "dados": {
    "total_registros_processados": 12500,
    "media_registros_por_consulta": 833.3,
    "registros_por_segundo_medio": 18.4
  }
}
```

#### `/performance-metrics`
Retorna todas as métricas completas com estatísticas detalhadas.

## Como Usar

### 1. Execução Normal
As métricas são coletadas automaticamente sempre que você usar a API:

```bash
# Consulta síncrona (será medida automaticamente)
curl -X POST "http://localhost:8000/consultar" \
  -H "Content-Type: application/json" \
  -d '{"data_inicio": "2023-01-01", "data_fim": "2023-03-31"}'

# Consulta assíncrona (será medida automaticamente)
curl -X POST "http://localhost:8000/consultar" \
  -H "Content-Type: application/json" \
  -d '{"data_inicio": "2021-01-01", "data_fim": "2023-12-31"}'
```

### 2. Visualização das Métricas
```bash
# Resumo estatístico
curl "http://localhost:8000/performance-summary"

# Métricas completas
curl "http://localhost:8000/performance-metrics"
```

### 3. Script de Exemplo
Execute o script de exemplo para gerar dados de teste:

```bash
python exemplo_metricas.py
```

## Análise dos Dados

### Principais Métricas para Análise
1. **Tempo Médio por Ano**: Identifica anos que demoram mais para processar
2. **Taxa de Sucesso**: Monitora a confiabilidade da API
3. **Registros por Segundo**: Mede a eficiência do processamento
4. **Tempo por Etapa**: Identifica gargalos (navegador, formulário, download, etc.)

### Uso do CSV para Análise Avançada
O arquivo CSV pode ser importado em ferramentas como:
- **Excel/Google Sheets**: Para análises básicas e gráficos
- **Python/Pandas**: Para análises estatísticas avançadas
- **Power BI/Tableau**: Para dashboards interativos

### Exemplo de Análise em Python
```python
import pandas as pd
import matplotlib.pyplot as plt

# Carrega as métricas
df = pd.read_csv('performance_metrics.csv')

# Análise por ano
tempo_por_ano = df.groupby('ano_inicio')['tempo_total_segundos'].mean()
print("Tempo médio por ano:")
print(tempo_por_ano)

# Gráfico de performance ao longo do tempo
df['timestamp'] = pd.to_datetime(df['timestamp'])
plt.figure(figsize=(12, 6))
plt.plot(df['timestamp'], df['tempo_total_segundos'])
plt.title('Tempo de Processamento ao Longo do Tempo')
plt.xlabel('Data/Hora')
plt.ylabel('Tempo (segundos)')
plt.show()
```

## Configuração

### Personalizar Local do CSV
```python
from app.utils.performance_tracker import PerformanceTracker

# Cria tracker com caminho personalizado
tracker = PerformanceTracker(csv_path="/caminho/personalizado/metricas.csv")
```

### Desabilitar Rastreamento
Para desabilitar temporariamente o rastreamento, você pode comentar as chamadas para `performance_tracker.salvar_metrica()` nos serviços.

## Monitoramento em Produção

### Alertas Recomendados
1. **Tempo Médio > 60s**: Possível problema de performance
2. **Taxa de Sucesso < 90%**: Problema de confiabilidade
3. **Sem dados por > 1h**: Possível problema na API

### Rotação de Logs
Configure rotação automática do CSV para evitar arquivos muito grandes:
```python
import os
from datetime import datetime

# Exemplo de rotação diária
if os.path.getsize('performance_metrics.csv') > 10_000_000:  # 10MB
    backup_name = f"performance_metrics_{datetime.now().strftime('%Y%m%d')}.csv"
    os.rename('performance_metrics.csv', backup_name)
```

## Troubleshooting

### Arquivo CSV não é criado
- Verifique permissões de escrita no diretório
- Verifique se o import do `performance_tracker` está correto

### Métricas não aparecem nos endpoints
- Confirme que as consultas estão sendo executadas
- Verifique os logs da aplicação para erros

### Performance degradada
- O rastreamento adiciona ~0.1s por operação
- Para alta concorrência, considere usar buffer em memória
