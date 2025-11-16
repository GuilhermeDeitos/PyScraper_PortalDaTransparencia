import pytest
from app.Services.query_optimizer import QueryOptimizer, PeriodoAno

class TestQueryOptimizer:
    
    @pytest.fixture
    def optimizer(self, mocker):
        opt = QueryOptimizer()
        mocker.patch.object(
            opt.consulta_local, 
            'verificar_disponibilidade', 
            return_value=True
        )
        return opt
    
    def test_calcular_periodo_mesmo_ano(self, optimizer):
        periodo = optimizer.calcular_periodo_ano(2023, 2023, 6, 2023, 12)
        assert periodo.ano == 2023
        assert periodo.mes_inicio == 6
        assert periodo.mes_fim == 12
    
    def test_calcular_periodo_primeiro_ano(self, optimizer):
        periodo = optimizer.calcular_periodo_ano(2023, 2023, 6, 2024, 3)
        assert periodo.mes_inicio == 6
        assert periodo.mes_fim == 12
    
    def test_calcular_periodo_ultimo_ano(self, optimizer):
        periodo = optimizer.calcular_periodo_ano(2024, 2023, 6, 2024, 3)
        assert periodo.mes_inicio == 1
        assert periodo.mes_fim == 3
    
    def test_calcular_periodo_ano_intermediario(self, optimizer):
        periodo = optimizer.calcular_periodo_ano(2024, 2023, 6, 2025, 3)
        assert periodo.mes_inicio == 1
        assert periodo.mes_fim == 12
    
    def test_definir_estrategia(self, optimizer):
        estrategias = optimizer.definir_estrategia(2023, 1, 2024, 12)
        
        assert len(estrategias) == 2
        assert 2023 in estrategias
        assert 2024 in estrategias
        assert estrategias[2023].usar_dados_locais is True
    
    def test_calcular_estatisticas(self, optimizer):
        estrategias = optimizer.definir_estrategia(2023, 1, 2024, 12)
        anos_locais, anos_scraper = optimizer.calcular_estatisticas(estrategias)
        
        assert anos_locais == 2
        assert anos_scraper == 0