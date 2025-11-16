import pytest
from app.Services.form_handler import FormHandler

class TestFormHandler:
    
    def test_constantes_definidas(self):
        assert FormHandler.ORGAO_CODIGO == "45"
        assert "UniqueKey" in FormHandler.ORGAO_VALUE
    
    def test_preencher_ano(self, mocker):
        mock_driver = mocker.Mock()
        mock_executar_js = mocker.patch(
            "app.Services.form_handler.executar_javascript_seguro"
        )
        
        handler = FormHandler(mock_driver, "test_id")
        handler._preencher_ano(2023)
        
        mock_executar_js.assert_called_once()
        call_args = mock_executar_js.call_args[0]
        assert "2023" in call_args[1]
    
    def test_marcar_checkbox(self, mocker):
        mock_driver = mocker.Mock()
        mock_executar_js = mocker.patch(
            "app.Services.form_handler.executar_javascript_seguro"
        )
        
        handler = FormHandler(mock_driver, "test_id")
        handler._marcar_checkbox("id_teste", "teste")
        
        mock_executar_js.assert_called_once()
        call_args = mock_executar_js.call_args[0]
        assert "id_teste" in call_args[1]
        assert "checked = true" in call_args[1]