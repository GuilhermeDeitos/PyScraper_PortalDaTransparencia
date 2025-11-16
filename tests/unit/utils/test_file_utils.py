import pytest
import os
import tempfile
import time
from pathlib import Path
from app.utils.file_utils import (
    criar_diretorio_temporario,
    obter_arquivos_diretorio,
    obter_arquivos_mais_recentes,
    limpar_diretorio,
    remover_diretorio
)

class TestCriarDiretorioTemporario:
    
    def test_criar_diretorio_sem_subdir(self):
        dir_path = criar_diretorio_temporario()
        assert os.path.exists(dir_path)
        assert "scraper_downloads" in dir_path
        remover_diretorio(dir_path)
    
    def test_criar_diretorio_com_subdir(self):
        dir_path = criar_diretorio_temporario("teste_subdir")
        assert os.path.exists(dir_path)
        assert "teste_subdir" in dir_path
        remover_diretorio(dir_path)
    
    def test_criar_diretorio_ja_existente_nao_falha(self):
        dir_path = criar_diretorio_temporario("subdir_existente")
        dir_path_2 = criar_diretorio_temporario("subdir_existente")
        assert dir_path == dir_path_2
        assert os.path.exists(dir_path)
        remover_diretorio(dir_path)

class TestObterArquivosDiretorio:
    
    def test_obter_arquivos_diretorio_vazio(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            arquivos = obter_arquivos_diretorio(tmpdir)
            assert arquivos == []
    
    def test_obter_arquivos_diretorio_com_arquivos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "arquivo1.txt").touch()
            Path(tmpdir, "arquivo2.txt").touch()
            
            arquivos = obter_arquivos_diretorio(tmpdir)
            assert len(arquivos) == 2
    
    def test_obter_arquivos_com_padrao(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "arquivo1.txt").touch()
            Path(tmpdir, "arquivo2.xls").touch()
            
            arquivos = obter_arquivos_diretorio(tmpdir, "*.xls")
            assert len(arquivos) == 1
            assert arquivos[0].endswith(".xls")

class TestObterArquivosMaisRecentes:
    
    def test_obter_mais_recente_retorna_ultimo_modificado(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            arquivo1 = Path(tmpdir, "arquivo1.xls")
            arquivo2 = Path(tmpdir, "arquivo2.xls")
            
            arquivo1.touch()
            time.sleep(0.1)
            arquivo2.touch()
            
            recentes = obter_arquivos_mais_recentes(tmpdir, ".xls", 1)
            assert len(recentes) == 1
            assert str(arquivo2) in recentes[0]
    
    def test_obter_multiplos_arquivos_recentes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                Path(tmpdir, f"arquivo{i}.xls").touch()
                time.sleep(0.1)
            
            recentes = obter_arquivos_mais_recentes(tmpdir, ".xls", 2)
            assert len(recentes) == 2

class TestLimparDiretorio:
    
    def test_limpar_diretorio_remove_arquivos(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "arquivo1.txt").touch()
            Path(tmpdir, "arquivo2.txt").touch()
            
            limpar_diretorio(tmpdir)
            
            arquivos = obter_arquivos_diretorio(tmpdir)
            assert len(arquivos) == 0
    
    def test_limpar_diretorio_inexistente_nao_falha(self):
        limpar_diretorio("/diretorio/que/nao/existe")

class TestRemoverDiretorio:
    
    def test_remover_diretorio_existente(self):
        tmpdir = tempfile.mkdtemp()
        Path(tmpdir, "arquivo.txt").touch()
        
        remover_diretorio(tmpdir)
        assert not os.path.exists(tmpdir)
    
    def test_remover_diretorio_inexistente_nao_falha(self):
        remover_diretorio("/diretorio/que/nao/existe")