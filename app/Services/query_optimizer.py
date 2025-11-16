import logging
from typing import Dict, Tuple
from dataclasses import dataclass
from app.Services.consulta_local import ConsultaLocal

logger = logging.getLogger(__name__)

@dataclass
class PeriodoAno:
    ano: int
    mes_inicio: int
    mes_fim: int

@dataclass
class EstrategiaProcessamento:
    periodo: PeriodoAno
    usar_dados_locais: bool
    
    @property
    def fonte(self) -> str:
        return "local" if self.usar_dados_locais else "scraper"

class QueryOptimizer:
    """Otimiza estratégia de consulta entre dados locais e scraper."""
    
    def __init__(self):
        self.consulta_local = ConsultaLocal()
    
    def calcular_periodo_ano(
        self, 
        ano: int, 
        ano_inicio: int, 
        mes_inicio: int, 
        ano_fim: int, 
        mes_fim: int
    ) -> PeriodoAno:
        """Calcula o período de meses para um ano específico."""
        if ano == ano_inicio and ano == ano_fim:
            return PeriodoAno(ano, mes_inicio, mes_fim)
        elif ano == ano_inicio:
            return PeriodoAno(ano, mes_inicio, 12)
        elif ano == ano_fim:
            return PeriodoAno(ano, 1, mes_fim)
        else:
            return PeriodoAno(ano, 1, 12)
    
    def definir_estrategia(
        self, 
        ano_inicio: int, 
        mes_inicio: int, 
        ano_fim: int, 
        mes_fim: int
    ) -> Dict[int, EstrategiaProcessamento]:
        """Define a estratégia de processamento para cada ano."""
        estrategias = {}
        
        for ano in range(ano_inicio, ano_fim + 1):
            periodo = self.calcular_periodo_ano(
                ano, ano_inicio, mes_inicio, ano_fim, mes_fim
            )
            
            usar_dados_locais = self.consulta_local.verificar_disponibilidade(
                ano, periodo.mes_inicio, periodo.mes_fim
            )
            
            estrategias[ano] = EstrategiaProcessamento(periodo, usar_dados_locais)
            
            logger.debug(
                f"Ano {ano}: {periodo.mes_inicio:02d}-{periodo.mes_fim:02d} via {estrategias[ano].fonte}"
            )
        
        return estrategias
    
    def calcular_estatisticas(
        self, 
        estrategias: Dict[int, EstrategiaProcessamento]
    ) -> Tuple[int, int]:
        """Calcula estatísticas de otimização."""
        anos_locais = sum(1 for est in estrategias.values() if est.usar_dados_locais)
        anos_scraper = len(estrategias) - anos_locais
        return anos_locais, anos_scraper