"""
Utilitário para rastreamento de performance da API.
Coleta métricas de tempo de processamento e salva em arquivo CSV.
"""
import time
import csv
import os
import logging
import threading
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class PerformanceMetric:
    """Classe para armazenar métricas de performance"""
    timestamp: str
    endpoint: str
    operation: str
    ano_inicio: int
    ano_fim: int
    mes_inicio: str
    mes_fim: str
    tempo_total_segundos: float
    tempo_scraping_segundos: float
    tempo_processamento_segundos: float
    numero_registros: int
    sucesso: bool
    erro_descricao: Optional[str] = None
    id_consulta: Optional[str] = None
    thread_id: Optional[str] = None

class PerformanceTracker:
    """Classe para rastrear performance da API e salvar em CSV"""
    
    def __init__(self, csv_path: str = "performance_metrics.csv"):
        """
        Inicializa o tracker de performance.
        
        Args:
            csv_path: Caminho para o arquivo CSV onde as métricas serão salvas
        """
        self.csv_path = csv_path
        self._lock = threading.Lock()
        self._create_csv_if_not_exists()
    
    def _create_csv_if_not_exists(self):
        """Cria o arquivo CSV com cabeçalhos se não existir"""
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, 'w', newline='', encoding='utf-8') as file:
                writer = csv.DictWriter(file, fieldnames=self._get_csv_headers())
                writer.writeheader()
            logger.info(f"Arquivo CSV de métricas criado: {self.csv_path}")
    
    def _get_csv_headers(self) -> list:
        """Retorna os cabeçalhos do CSV baseados na classe PerformanceMetric"""
        return [
            'timestamp', 'endpoint', 'operation', 'ano_inicio', 'ano_fim',
            'mes_inicio', 'mes_fim', 'tempo_total_segundos', 'tempo_scraping_segundos',
            'tempo_processamento_segundos', 'numero_registros', 'sucesso',
            'erro_descricao', 'id_consulta', 'thread_id'
        ]
    
    def salvar_metrica(self, metric: PerformanceMetric):
        """
        Salva uma métrica no arquivo CSV.
        
        Args:
            metric: Instância de PerformanceMetric com os dados da métrica
        """
        try:
            with self._lock:
                with open(self.csv_path, 'a', newline='', encoding='utf-8') as file:
                    writer = csv.DictWriter(file, fieldnames=self._get_csv_headers())
                    writer.writerow(asdict(metric))
                
                logger.debug(f"Métrica salva no CSV: {metric.operation} - {metric.tempo_total_segundos:.2f}s")
        
        except Exception as e:
            logger.error(f"Erro ao salvar métrica no CSV: {e}")
    
    def criar_metrica(
        self,
        endpoint: str,
        operation: str,
        ano_inicio: int,
        ano_fim: int,
        mes_inicio: str,
        mes_fim: str,
        tempo_total: float,
        tempo_scraping: float = 0.0,
        tempo_processamento: float = 0.0,
        numero_registros: int = 0,
        sucesso: bool = True,
        erro_descricao: Optional[str] = None,
        id_consulta: Optional[str] = None
    ) -> PerformanceMetric:
        """
        Cria uma instância de PerformanceMetric com timestamp atual.
        
        Args:
            endpoint: Nome do endpoint da API
            operation: Tipo de operação (ex: 'consulta_sincrona', 'consulta_assincrona')
            ano_inicio: Ano inicial da consulta
            ano_fim: Ano final da consulta
            mes_inicio: Mês inicial da consulta
            mes_fim: Mês final da consulta
            tempo_total: Tempo total da operação em segundos
            tempo_scraping: Tempo gasto apenas no scraping em segundos
            tempo_processamento: Tempo gasto no processamento dos dados em segundos
            numero_registros: Número de registros retornados
            sucesso: Se a operação foi bem-sucedida
            erro_descricao: Descrição do erro, se houver
            id_consulta: ID da consulta (para operações assíncronas)
            
        Returns:
            Instância de PerformanceMetric
        """
        return PerformanceMetric(
            timestamp=datetime.now().isoformat(),
            endpoint=endpoint,
            operation=operation,
            ano_inicio=ano_inicio,
            ano_fim=ano_fim,
            mes_inicio=mes_inicio,
            mes_fim=mes_fim,
            tempo_total_segundos=tempo_total,
            tempo_scraping_segundos=tempo_scraping,
            tempo_processamento_segundos=tempo_processamento,
            numero_registros=numero_registros,
            sucesso=sucesso,
            erro_descricao=erro_descricao,
            id_consulta=id_consulta,
            thread_id=threading.current_thread().name
        )

class TimerContext:
    """Context manager para medir tempo de execução"""
    
    def __init__(self, name: str = "operation"):
        """
        Inicializa o context manager.
        
        Args:
            name: Nome da operação sendo medida
        """
        self.name = name
        self.start_time = None
        self.end_time = None
        self.duration = None
    
    def __enter__(self):
        """Inicia a medição de tempo"""
        self.start_time = time.time()
        logger.debug(f"Iniciando medição de tempo para: {self.name}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Finaliza a medição de tempo"""
        self.end_time = time.time()
        self.duration = self.end_time - self.start_time
        logger.debug(f"Tempo de execução para {self.name}: {self.duration:.2f} segundos")
    
    def get_duration(self) -> float:
        """Retorna a duração em segundos"""
        return self.duration if self.duration is not None else 0.0

# Instância global do tracker
performance_tracker = PerformanceTracker()

def track_performance(func):
    """
    Decorator para rastrear automaticamente a performance de funções.
    
    Args:
        func: Função a ser decorada
        
    Returns:
        Função decorada com rastreamento de performance
    """
    def wrapper(*args, **kwargs):
        with TimerContext(func.__name__) as timer:
            try:
                result = func(*args, **kwargs)
                # Aqui você pode adicionar lógica adicional para extrair métricas específicas
                return result
            except Exception as e:
                logger.error(f"Erro na função {func.__name__}: {e}")
                raise
    
    return wrapper
