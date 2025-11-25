import pytest
import os
import tempfile
import time
from pathlib import Path
from app.utils.file_utils import (
    criar_diretorio_temporario,
    criar_diretorio_download,
    criar_perfil_chrome,
    obter_arquivos_diretorio,
    obter_arquivos_mais_recentes,
    limpar_diretorio,
    remover_diretorio,
    verificar_diretorio_existe,
    verificar_arquivo_existe,
    obter_tamanho_diretorio,
    formatar_tamanho
)

class TestCriarDiretorioTemporario:
    
    def test_criar_diretorio_sem_subdir(self):
        """Testa criação de diretório temporário sem subdir."""
        dir_path = criar_diretorio_temporario()
        
        assert os.path.exists(dir_path)
        assert "scraper_temp" in dir_path
        
        remover_diretorio(dir_path)
    
    def test_criar_diretorio_com_subdir(self):
        """Testa criação de diretório temporário com subdir específico."""
        subdir = "teste_subdir"
        dir_path = criar_diretorio_temporario(subdir=subdir)
        
        assert os.path.exists(dir_path)
        assert subdir in dir_path
        
        # Limpar diretório pai também
        parent_dir = os.path.dirname(dir_path)
        remover_diretorio(parent_dir)
    
    def test_criar_diretorio_com_prefixo_customizado(self):
        """Testa criação com prefixo customizado."""
        prefixo = "custom_prefix"
        dir_path = criar_diretorio_temporario(prefixo=prefixo)
        
        assert os.path.exists(dir_path)
        assert prefixo in dir_path
        
        remover_diretorio(dir_path)
    
    def test_criar_diretorio_ja_existente_nao_falha(self):
        """Testa que não falha ao criar diretório já existente."""
        subdir = "subdir_existente"
        dir_path = criar_diretorio_temporario(subdir=subdir)
        
        # Criar novamente não deve falhar
        dir_path_2 = criar_diretorio_temporario(subdir=subdir)
        
        # Ambos devem existir e apontar para o mesmo local
        assert os.path.exists(dir_path)
        assert os.path.exists(dir_path_2)
        assert dir_path == dir_path_2
        
        parent_dir = os.path.dirname(dir_path)
        remover_diretorio(parent_dir)

class TestCriarDiretorioDownload:
    
    def test_criar_diretorio_download(self):
        """Testa criação de diretório de download."""
        scraper_id = "test123"
        dir_path = criar_diretorio_download(scraper_id)
        
        assert os.path.exists(dir_path)
        assert f"downloads_{scraper_id}" in dir_path
        
        remover_diretorio(dir_path)
    
    def test_cada_chamada_cria_diretorio_unico(self):
        """Testa que cada chamada cria diretório único."""
        scraper_id = "test456"
        
        dir_path_1 = criar_diretorio_download(scraper_id)
        time.sleep(0.01)  # Pequeno delay para garantir timestamp diferente
        dir_path_2 = criar_diretorio_download(scraper_id)
        
        assert dir_path_1 != dir_path_2
        assert os.path.exists(dir_path_1)
        assert os.path.exists(dir_path_2)
        
        remover_diretorio(dir_path_1)
        remover_diretorio(dir_path_2)

class TestCriarPerfilChrome:
    
    def test_criar_perfil_chrome(self):
        """Testa criação de perfil Chrome."""
        scraper_id = "test789"
        profile_dir = criar_perfil_chrome(scraper_id)
        
        assert os.path.exists(profile_dir)
        assert f"chrome_profile_{scraper_id}" in profile_dir
        
        remover_diretorio(profile_dir)

class TestObterArquivosDiretorio:
    
    def test_obter_arquivos_diretorio_vazio(self):
        """Testa obter arquivos de diretório vazio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            arquivos = obter_arquivos_diretorio(tmpdir)
            assert arquivos == []
    
    def test_obter_arquivos_diretorio_com_arquivos(self):
        """Testa obter todos os arquivos de diretório."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "arquivo1.txt").touch()
            Path(tmpdir, "arquivo2.txt").touch()
            
            arquivos = obter_arquivos_diretorio(tmpdir)
            assert len(arquivos) == 2
    
    def test_obter_arquivos_com_padrao(self):
        """Testa obter arquivos com padrão específico."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "arquivo1.txt").touch()
            Path(tmpdir, "arquivo2.xls").touch()
            Path(tmpdir, "arquivo3.xls").touch()
            
            arquivos = obter_arquivos_diretorio(tmpdir, "*.xls")
            assert len(arquivos) == 2
            for arquivo in arquivos:
                assert arquivo.endswith(".xls")
    
    def test_obter_arquivos_diretorio_inexistente(self):
        """Testa obter arquivos de diretório que não existe."""
        arquivos = obter_arquivos_diretorio("/diretorio/que/nao/existe")
        assert arquivos == []

class TestObterArquivosMaisRecentes:
    
    def test_obter_mais_recente_retorna_ultimo_modificado(self):
        """Testa que retorna arquivo mais recentemente modificado."""
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
        """Testa obter múltiplos arquivos mais recentes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(3):
                Path(tmpdir, f"arquivo{i}.xls").touch()
                time.sleep(0.05)
            
            recentes = obter_arquivos_mais_recentes(tmpdir, ".xls", 2)
            assert len(recentes) == 2
    
    def test_obter_mais_recentes_sem_arquivos_correspondentes(self):
        """Testa quando não há arquivos com extensão especificada."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "arquivo.txt").touch()
            
            recentes = obter_arquivos_mais_recentes(tmpdir, ".xls", 1)
            assert recentes == []

class TestLimparDiretorio:
    
    def test_limpar_diretorio_remove_arquivos(self):
        """Testa que limpar diretório remove arquivos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "arquivo1.txt").touch()
            Path(tmpdir, "arquivo2.txt").touch()
            
            resultado = limpar_diretorio(tmpdir)
            
            assert resultado is True
            arquivos = obter_arquivos_diretorio(tmpdir)
            assert len(arquivos) == 0
    
    def test_limpar_diretorio_preserva_subdiretorios_por_padrao(self):
        """Testa que subdiretórios são preservados por padrão."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "arquivo.txt").touch()
            os.makedirs(os.path.join(tmpdir, "subdir"))
            
            limpar_diretorio(tmpdir, remover_subdiretorios=False)
            
            assert len(os.listdir(tmpdir)) == 1
            assert os.path.isdir(os.path.join(tmpdir, "subdir"))
    
    def test_limpar_diretorio_remove_subdiretorios_quando_solicitado(self):
        """Testa remoção de subdiretórios quando solicitado."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "arquivo.txt").touch()
            os.makedirs(os.path.join(tmpdir, "subdir"))
            
            limpar_diretorio(tmpdir, remover_subdiretorios=True)
            
            assert len(os.listdir(tmpdir)) == 0
    
    def test_limpar_diretorio_inexistente_retorna_true(self):
        """Testa que não falha ao limpar diretório inexistente."""
        resultado = limpar_diretorio("/diretorio/que/nao/existe")
        assert resultado is True

class TestRemoverDiretorio:
    
    def test_remover_diretorio_existente(self):
        """Testa remoção de diretório existente."""
        tmpdir = tempfile.mkdtemp()
        Path(tmpdir, "arquivo.txt").touch()
        
        resultado = remover_diretorio(tmpdir)
        
        assert resultado is True
        assert not os.path.exists(tmpdir)
    
    def test_remover_diretorio_inexistente_retorna_true(self):
        """Testa que não falha ao remover diretório inexistente."""
        resultado = remover_diretorio("/diretorio/que/nao/existe")
        assert resultado is True
    
    def test_remover_diretorio_com_subdiretorios(self):
        """Testa remoção de diretório com conteúdo."""
        tmpdir = tempfile.mkdtemp()
        subdir = os.path.join(tmpdir, "subdir")
        os.makedirs(subdir)
        Path(subdir, "arquivo.txt").touch()
        
        resultado = remover_diretorio(tmpdir)
        
        assert resultado is True
        assert not os.path.exists(tmpdir)

class TestVerificarDiretorioExiste:
    
    def test_diretorio_existente(self):
        """Testa verificação de diretório existente."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert verificar_diretorio_existe(tmpdir) is True
    
    def test_diretorio_inexistente(self):
        """Testa verificação de diretório inexistente."""
        assert verificar_diretorio_existe("/diretorio/que/nao/existe") is False
    
    def test_arquivo_nao_e_diretorio(self):
        """Testa que arquivo não é considerado diretório."""
        with tempfile.NamedTemporaryFile() as tmpfile:
            assert verificar_diretorio_existe(tmpfile.name) is False

class TestVerificarArquivoExiste:
    
    def test_arquivo_existente(self):
        """Testa verificação de arquivo existente."""
        with tempfile.NamedTemporaryFile() as tmpfile:
            assert verificar_arquivo_existe(tmpfile.name) is True
    
    def test_arquivo_inexistente(self):
        """Testa verificação de arquivo inexistente."""
        assert verificar_arquivo_existe("/arquivo/que/nao/existe.txt") is False
    
    def test_diretorio_nao_e_arquivo(self):
        """Testa que diretório não é considerado arquivo."""
        with tempfile.TemporaryDirectory() as tmpdir:
            assert verificar_arquivo_existe(tmpdir) is False

class TestObterTamanhoDiretorio:
    
    def test_tamanho_diretorio_vazio(self):
        """Testa tamanho de diretório vazio."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tamanho = obter_tamanho_diretorio(tmpdir)
            assert tamanho == 0
    
    def test_tamanho_diretorio_com_arquivos(self):
        """Testa tamanho de diretório com arquivos."""
        with tempfile.TemporaryDirectory() as tmpdir:
            arquivo = Path(tmpdir, "teste.txt")
            arquivo.write_text("Conteúdo de teste" * 100)
            
            tamanho = obter_tamanho_diretorio(tmpdir)
            assert tamanho > 0
    
    def test_tamanho_diretorio_inexistente(self):
        """Testa tamanho de diretório inexistente."""
        tamanho = obter_tamanho_diretorio("/diretorio/que/nao/existe")
        assert tamanho == 0

class TestFormatarTamanho:
    
    def test_formatar_bytes(self):
        """Testa formatação de tamanho em bytes."""
        assert "B" in formatar_tamanho(512)
    
    def test_formatar_kilobytes(self):
        """Testa formatação em kilobytes."""
        resultado = formatar_tamanho(1024)
        assert "KB" in resultado
    
    def test_formatar_megabytes(self):
        """Testa formatação em megabytes."""
        resultado = formatar_tamanho(1024 * 1024)
        assert "MB" in resultado
    
    def test_formatar_gigabytes(self):
        """Testa formatação em gigabytes."""
        resultado = formatar_tamanho(1024 * 1024 * 1024)
        assert "GB" in resultado
    
    def test_formatar_zero(self):
        """Testa formatação de zero bytes."""
        resultado = formatar_tamanho(0)
        assert "0.00 B" == resultado