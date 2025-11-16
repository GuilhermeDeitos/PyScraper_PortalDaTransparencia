import pytest
from datetime import datetime
from app.utils.date_utils import (
    obter_range_anos,
    formatar_mes,
    split_data,
    data_valida,
    formatar_data_api,
    formatar_periodo_texto,
    obter_mes_atual,
    obter_ano_atual,
    dict_mes_numero,
    dict_mes_texto_para_numero
)

class TestObterRangeAnos:
    
    def test_mesmo_ano(self):
        ano_i, ano_f = obter_range_anos("01/2020", "12/2020")
        assert ano_i == 2020
        assert ano_f == 2020
    
    def test_anos_diferentes(self):
        ano_i, ano_f = obter_range_anos("06/2018", "03/2023")
        assert ano_i == 2018
        assert ano_f == 2023

class TestFormatarMes:
    
    @pytest.mark.parametrize("mes_input, esperado", [
        (1, "01"),
        (9, "09"),
        (10, "10"),
        (12, "12"),
        ("5", "05"),
    ])
    def test_formatar_mes_correto(self, mes_input, esperado):
        assert formatar_mes(mes_input) == esperado

class TestSplitData:
    
    def test_split_data_valida(self):
        mes, ano = split_data("06/2022")
        assert mes == 6
        assert ano == 2022
    
    def test_mes_invalido_levanta_erro(self):
        with pytest.raises(ValueError, match="Mês inválido"):
            split_data("13/2022")
    
    def test_mes_zero_levanta_erro(self):
        with pytest.raises(ValueError, match="Mês inválido"):
            split_data("00/2022")
    
    def test_ano_abaixo_limite_levanta_erro(self):
        with pytest.raises(ValueError, match="Ano fora do intervalo"):
            split_data("06/2001")
    
    def test_ano_acima_limite_levanta_erro(self):
        with pytest.raises(ValueError, match="Ano fora do intervalo"):
            split_data("06/2024")
    
    def test_formato_invalido_levanta_erro(self):
        with pytest.raises(ValueError):
            split_data("2022/06")

class TestDataValida:
    
    @pytest.mark.parametrize("data_valida_str", [
        "01/2020",
        "12/2023",
        "06/2015",
    ])
    def test_datas_validas(self, data_valida_str):
        assert data_valida(data_valida_str) is True
    
    @pytest.mark.parametrize("data_invalida", [
        "13/2020",
        "00/2020",
        "2020/01",
        "01-2020",
        "1/2020",
        "01/20",
        "abc",
        "",
    ])
    def test_datas_invalidas(self, data_invalida):
        assert data_valida(data_invalida) is False

class TestFormatarDataApi:
    
    def test_formatar_data_api_correto(self):
        resultado = formatar_data_api("06/2022")
        assert resultado == "2022-06"
    
    def test_data_invalida_levanta_erro(self):
        with pytest.raises(ValueError, match="Formato de data inválido"):
            formatar_data_api("13/2022")

class TestFormatarPeriodoTexto:
    
    def test_mesmo_mes_ano(self):
        resultado = formatar_periodo_texto(6, 2022, 6, 2022)
        assert resultado == "JUNHO/2022"
    
    def test_meses_diferentes_mesmo_ano(self):
        resultado = formatar_periodo_texto(1, 2022, 6, 2022)
        assert resultado == "JANEIRO a JUNHO/2022"
    
    def test_anos_diferentes(self):
        resultado = formatar_periodo_texto(12, 2020, 3, 2023)
        assert resultado == "DEZEMBRO/2020 a MARÇO/2023"

class TestDicionariosMes:
    
    def test_dict_mes_numero_completo(self):
        assert len(dict_mes_numero) == 12
        assert dict_mes_numero[1] == "JANEIRO"
        assert dict_mes_numero[12] == "DEZEMBRO"
    
    def test_dict_mes_texto_inverso(self):
        assert dict_mes_texto_para_numero["JANEIRO"] == 1
        assert dict_mes_texto_para_numero["DEZEMBRO"] == 12

class TestObterDataAtual:
    
    def test_obter_mes_atual_retorna_inteiro(self):
        mes = obter_mes_atual()
        assert isinstance(mes, int)
        assert 1 <= mes <= 12
    
    def test_obter_ano_atual_retorna_inteiro(self):
        ano = obter_ano_atual()
        assert isinstance(ano, int)
        assert ano >= 2024