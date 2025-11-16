import pytest
from app.utils.validators import validar_parametros, validar_id_consulta

class TestValidarParametros:
    
    def test_parametros_validos(self):
        mes_i, ano_i, mes_f, ano_f = validar_parametros("01/2020", "12/2023")
        assert mes_i == 1
        assert ano_i == 2020
        assert mes_f == 12
        assert ano_f == 2023
    
    def test_mesmo_mes_ano_valido(self):
        mes_i, ano_i, mes_f, ano_f = validar_parametros("06/2022", "06/2022")
        assert mes_i == 6
        assert ano_i == 2022
        assert mes_f == 6
        assert ano_f == 2022
    
    def test_data_inicio_ausente_levanta_erro(self):
        with pytest.raises(ValueError, match="obrigatórios"):
            validar_parametros("", "12/2023")
    
    def test_data_fim_ausente_levanta_erro(self):
        with pytest.raises(ValueError, match="obrigatórios"):
            validar_parametros("01/2020", "")
    
    def test_ambas_datas_ausentes_levanta_erro(self):
        with pytest.raises(ValueError, match="obrigatórios"):
            validar_parametros(None, None)
    
    def test_formato_invalido_levanta_erro(self):
        with pytest.raises(ValueError, match="Formato de data inválido"):
            validar_parametros("01-2020", "12/2023")
    
    def test_data_inicio_maior_que_fim_levanta_erro(self):
        with pytest.raises(ValueError, match="não pode ser maior"):
            validar_parametros("12/2023", "01/2020")
    
    def test_mes_inicio_maior_mesmo_ano_levanta_erro(self):
        with pytest.raises(ValueError, match="não pode ser maior"):
            validar_parametros("12/2023", "01/2023")

class TestValidarIdConsulta:
    
    @pytest.mark.parametrize("uuid_valido", [
        "123e4567-e89b-12d3-a456-426614174000",
        "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
        "00000000-0000-0000-0000-000000000000",
    ])
    def test_uuid_valido_retorna_true(self, uuid_valido):
        assert validar_id_consulta(uuid_valido) is True
    
    def test_uuid_maiusculo_retorna_true(self):
        assert validar_id_consulta("123E4567-E89B-12D3-A456-426614174000") is True
    
    @pytest.mark.parametrize("uuid_invalido", [
        "123e4567-e89b-12d3-a456",
        "123e4567-e89b-12d3-a456-42661417400g",
        "não-é-um-uuid",
        "",
        "123e4567e89b12d3a456426614174000",
    ])
    def test_uuid_invalido_retorna_false(self, uuid_invalido):
        assert validar_id_consulta(uuid_invalido) is False