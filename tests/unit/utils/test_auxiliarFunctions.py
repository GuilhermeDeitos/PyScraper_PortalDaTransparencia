import pytest
from app.utils.auxiliarFunctions import (
    formatar_valor_monetario,
    extrair_numero,
    limpar_texto,
    validar_range_valores
)

class TestFormatarValorMonetario:
    
    @pytest.mark.parametrize("valor, esperado", [
        (1000.50, "R$ 1.000,50"),
        (1000000, "R$ 1.000.000,00"),
        (0, "R$ 0,00"),
        (10.5, "R$ 10,50"),
    ])
    def test_formatar_valores_positivos(self, valor, esperado):
        resultado = formatar_valor_monetario(valor)
        assert resultado == esperado
    
    def test_valor_negativo_formata_corretamente(self):
        resultado = formatar_valor_monetario(-1000.50)
        assert "1.000,50" in resultado

class TestExtrairNumero:
    
    @pytest.mark.parametrize("texto, esperado", [
        ("R$ 1.000,50", 1000.50),
        ("1000.50", 1000.50),
        ("texto 123 mais texto", 123.0),
        ("sem numeros", None),
    ])
    def test_extrai_numeros_texto(self, texto, esperado):
        resultado = extrair_numero(texto)
        if esperado is None:
            assert resultado is None
        else:
            assert abs(resultado - esperado) < 0.01

class TestLimparTexto:
    
    @pytest.mark.parametrize("texto, esperado", [
        ("  texto com espaços  ", "texto com espaços"),
        ("TEXTO\nCOM\nQUEBRAS", "TEXTO COM QUEBRAS"),
        ("texto\t\tcom\ttabs", "texto com tabs"),
    ])
    def test_limpa_texto_corretamente(self, texto, esperado):
        resultado = limpar_texto(texto)
        assert resultado == esperado

class TestValidarRangeValores:
    
    def test_valores_dentro_range_retorna_true(self):
        assert validar_range_valores(50, 0, 100) is True
    
    def test_valor_fora_range_retorna_false(self):
        assert validar_range_valores(150, 0, 100) is False
    
    def test_valor_igual_limite_retorna_true(self):
        assert validar_range_valores(100, 0, 100) is True