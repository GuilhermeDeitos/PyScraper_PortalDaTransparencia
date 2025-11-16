import pytest
from app.Services.data_validator import DataValidator

class TestDataValidator:
    
    @pytest.fixture
    def validator(self):
        return DataValidator()
    
    def test_validar_registro_valido(self, validator):
        registro = {
            "UNIDADE_ORCAMENTARIA": "UNIDADE TESTE",
            "GRUPO_NATUREZA_DESPESA": "DESPESAS CORRENTES",
            "ORIGEM_RECURSOS": "RECURSOS ORDINARIOS"
        }
        assert validator._validar_registro(registro) is True
    
    def test_validar_grupo_natureza_invalido(self, validator):
        registro = {
            "GRUPO_NATUREZA_DESPESA": "O - ORIGEM RECURSOS"
        }
        assert validator._validar_registro(registro) is False
    
    def test_validar_origem_recursos_invalida(self, validator):
        registro = {
            "ORIGEM_RECURSOS": "1234567890"
        }
        assert validator._validar_registro(registro) is False
    
    def test_validar_dados_ano(self, validator):
        dados = [
            {"GRUPO_NATUREZA_DESPESA": "DESPESAS CORRENTES"},
            {"GRUPO_NATUREZA_DESPESA": "O - ORIGEM"},
            {"ORIGEM_RECURSOS": "ORDINARIOS"}
        ]
        
        resultado = validator.validar_dados_ano(dados, 2023)
        
        assert len(resultado) == 2
        assert all(r['_ano_validado'] == 2023 for r in resultado)
    
    def test_validar_taxa_sucesso_acima_minimo(self, validator):
        dados_validos = [{}] * 9
        dados_totais = [{}] * 10
        
        assert validator.validar_taxa_sucesso(dados_validos, dados_totais) is True
    
    def test_validar_taxa_sucesso_abaixo_minimo(self, validator):
        dados_validos = [{}] * 7
        dados_totais = [{}] * 10
        
        assert validator.validar_taxa_sucesso(dados_validos, dados_totais) is False