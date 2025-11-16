import pytest
from app.utils.browser_utils import (
    configurar_chrome_options,
    executar_javascript_seguro
)

class TestConfigurarChromeOptions:
    
    def test_configurar_headless_true(self):
        options = configurar_chrome_options(headless=True)
        assert "--headless" in options.arguments
    
    def test_configurar_headless_false(self):
        options = configurar_chrome_options(headless=False)
        assert "--headless" not in options.arguments
    
    def test_configuracoes_padrao_presentes(self):
        options = configurar_chrome_options()
        args = options.arguments
        
        assert "--disable-gpu" in args
        assert "--no-sandbox" in args
        assert "--disable-dev-shm-usage" in args
    
    def test_configurar_download_dir(self):
        download_dir = "/tmp/downloads"
        options = configurar_chrome_options(download_dir=download_dir)
        
        prefs = options.experimental_options.get("prefs", {})
        assert prefs.get("download.default_directory") == download_dir
        assert prefs.get("download.prompt_for_download") is False

class TestExecutarJavascriptSeguro:
    
    def test_javascript_sucesso_retorna_resultado(self, mocker):
        mock_driver = mocker.Mock()
        mock_driver.execute_script.return_value = 42
        
        resultado = executar_javascript_seguro(mock_driver, "return 42;")
        assert resultado == 42
    
    def test_javascript_com_erro_retorna_none(self, mocker):
        mock_driver = mocker.Mock()
        mock_driver.execute_script.side_effect = Exception("Erro JS")
        
        resultado = executar_javascript_seguro(mock_driver, "script_invalido")
        assert resultado is None