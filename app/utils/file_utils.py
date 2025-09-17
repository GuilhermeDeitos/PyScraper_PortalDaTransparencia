"""
Utilitários para manipulação de arquivos.
"""
import os
import glob
import shutil
import tempfile
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

def criar_diretorio_temporario(subdir: str = None) -> str:
    """
    Cria um diretório temporário único para downloads.
    
    Args:
        subdir: Nome do subdiretório específico (opcional)
        
    Returns:
        Caminho completo do diretório criado
    """
    if subdir:
        # Usar o subdir fornecido dentro do temp
        temp_base = tempfile.gettempdir()
        download_dir = os.path.join(temp_base, "scraper_downloads", subdir)
    else:
        # Gerar nome único baseado em timestamp e UUID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        dir_name = f"scraper_{timestamp}_{unique_id}"
        temp_base = tempfile.gettempdir()
        download_dir = os.path.join(temp_base, "scraper_downloads", dir_name)
    
    # Criar o diretório se não existir
    os.makedirs(download_dir, exist_ok=True)
    
    return download_dir

def obter_arquivos_diretorio(diretorio: str, padrao: str = "*") -> List[str]:
    """
    Obtém a lista de arquivos em um diretório que correspondem a um padrão.
    
    Args:
        diretorio: Caminho do diretório
        padrao: Padrão de arquivos (ex: "*.xls")
        
    Returns:
        Lista de caminhos completos dos arquivos
    """
    padrao_busca = os.path.join(diretorio, padrao)
    arquivos = glob.glob(padrao_busca)
    return arquivos

def obter_arquivos_mais_recentes(diretorio: str, extensao: str = ".xls", quantidade: int = 1) -> List[str]:
    """
    Obtém os arquivos mais recentes em um diretório com base na data de modificação.
    
    Args:
        diretorio: Caminho do diretório
        extensao: Extensão dos arquivos a considerar
        quantidade: Quantidade de arquivos a retornar
        
    Returns:
        Lista com os caminhos dos arquivos mais recentes
    """
    padrao = f"*{extensao}"
    arquivos = obter_arquivos_diretorio(diretorio, padrao)
    
    # Ordena arquivos por data de modificação (mais recente primeiro)
    arquivos_ordenados = sorted(
        arquivos, 
        key=lambda x: os.path.getmtime(x), 
        reverse=True
    )
    
    return arquivos_ordenados[:quantidade]

def limpar_diretorio(diretorio: str) -> None:
    """
    Remove todos os arquivos de um diretório.
    
    Args:
        diretorio: Caminho do diretório a ser limpo
    """
    try:
        if os.path.exists(diretorio):
            for arquivo in os.listdir(diretorio):
                caminho = os.path.join(diretorio, arquivo)
                if os.path.isfile(caminho):
                    os.unlink(caminho)
            logger.debug(f"Diretório limpo: {diretorio}")
    except Exception as e:
        logger.error(f"Erro ao limpar diretório {diretorio}: {e}")

def remover_diretorio(diretorio: str) -> None:
    """Remove um diretório e todo seu conteúdo"""
    try:
        if os.path.exists(diretorio):
            shutil.rmtree(diretorio)
    except Exception as e:
        # Log erro mas não falha - diretório pode estar em uso
        print(f"Aviso: Não foi possível remover {diretorio}: {e}")