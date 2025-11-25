"""
Utilitários para manipulação de arquivos e diretórios.
Centraliza operações com sistema de arquivos para evitar duplicação.
"""
import os
import glob
import shutil
import tempfile
import logging
from typing import Optional, List
from datetime import datetime
import uuid

logger = logging.getLogger(__name__)

def criar_diretorio_temporario(prefixo: str = "scraper", subdir: Optional[str] = None) -> str:
    """
    Cria um diretório temporário único.
    
    Args:
        prefixo: Prefixo para o nome do diretório
        subdir: Nome do subdiretório específico (opcional)
        
    Returns:
        Caminho completo do diretório criado
    """
    temp_base = tempfile.gettempdir()
    
    if subdir:
        # Usar o subdir fornecido dentro do temp
        dir_path = os.path.join(temp_base, f"{prefixo}_temp", subdir)
    else:
        # Gerar nome único baseado em timestamp e UUID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        unique_id = str(uuid.uuid4())[:8]
        dir_name = f"{prefixo}_{timestamp}_{unique_id}"
        dir_path = os.path.join(temp_base, f"{prefixo}_temp", dir_name)
    
    # Criar o diretório se não existir
    os.makedirs(dir_path, exist_ok=True)
    logger.debug(f"Diretório temporário criado: {dir_path}")
    
    return dir_path

def criar_diretorio_download(scraper_id: str) -> str:
    """
    Cria diretório específico para downloads do scraper.
    
    Args:
        scraper_id: Identificador único do scraper
        
    Returns:
        Caminho do diretório de download
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dir_name = f"downloads_{scraper_id}_{timestamp}"
    
    # Usar /tmp para compatibilidade com containers
    base_dir = os.getenv('DOWNLOAD_DIR', '/tmp/chrome_downloads')
    download_path = os.path.join(base_dir, dir_name)
    
    os.makedirs(download_path, exist_ok=True)
    logger.info(f"Diretório de download criado: {download_path}")
    
    return download_path

def criar_perfil_chrome(scraper_id: str) -> str:
    """
    Cria diretório de perfil único para instância do Chrome.
    
    Args:
        scraper_id: Identificador único do scraper
        
    Returns:
        Caminho do diretório de perfil
    """
    profile_dir = os.path.join(tempfile.gettempdir(), f"chrome_profile_{scraper_id}")
    os.makedirs(profile_dir, exist_ok=True)
    logger.info(f"Perfil Chrome criado: {profile_dir}")
    
    return profile_dir

def obter_arquivos_diretorio(diretorio: str, padrao: str = "*") -> List[str]:
    """
    Obtém a lista de arquivos em um diretório que correspondem a um padrão.
    
    Args:
        diretorio: Caminho do diretório
        padrao: Padrão de arquivos (ex: "*.xls")
        
    Returns:
        Lista de caminhos completos dos arquivos
    """
    if not os.path.exists(diretorio):
        logger.warning(f"Diretório não existe: {diretorio}")
        return []
    
    padrao_busca = os.path.join(diretorio, padrao)
    arquivos = glob.glob(padrao_busca)
    
    logger.debug(f"Encontrados {len(arquivos)} arquivos em {diretorio} com padrão {padrao}")
    return arquivos

def obter_arquivos_mais_recentes(
    diretorio: str, 
    extensao: str = ".xls", 
    quantidade: int = 1
) -> List[str]:
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
    
    if not arquivos:
        logger.warning(f"Nenhum arquivo encontrado com extensão {extensao} em {diretorio}")
        return []
    
    # Ordena arquivos por data de modificação (mais recente primeiro)
    arquivos_ordenados = sorted(
        arquivos, 
        key=lambda x: os.path.getmtime(x), 
        reverse=True
    )
    
    arquivos_selecionados = arquivos_ordenados[:quantidade]
    logger.debug(f"Arquivos mais recentes: {arquivos_selecionados}")
    
    return arquivos_selecionados

def limpar_diretorio(diretorio: str, remover_subdiretorios: bool = False) -> bool:
    """
    Remove todos os arquivos de um diretório.
    
    Args:
        diretorio: Caminho do diretório a ser limpo
        remover_subdiretorios: Se True, remove também subdiretórios
        
    Returns:
        True se limpeza foi bem sucedida, False caso contrário
    """
    try:
        if not os.path.exists(diretorio):
            logger.debug(f"Diretório não existe, nada a limpar: {diretorio}")
            return True
        
        itens_removidos = 0
        for item in os.listdir(diretorio):
            caminho = os.path.join(diretorio, item)
            
            try:
                if os.path.isfile(caminho):
                    os.unlink(caminho)
                    itens_removidos += 1
                elif os.path.isdir(caminho) and remover_subdiretorios:
                    shutil.rmtree(caminho)
                    itens_removidos += 1
            except Exception as e:
                logger.warning(f"Erro ao remover {caminho}: {e}")
        
        logger.info(f"Diretório limpo: {diretorio} ({itens_removidos} itens removidos)")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao limpar diretório {diretorio}: {e}")
        return False

def remover_diretorio(diretorio: str, forcar: bool = False) -> bool:
    """
    Remove um diretório e todo seu conteúdo.
    
    Args:
        diretorio: Caminho do diretório a ser removido
        forcar: Se True, ignora erros e tenta forçar remoção
        
    Returns:
        True se remoção foi bem sucedida, False caso contrário
    """
    try:
        if not os.path.exists(diretorio):
            logger.debug(f"Diretório não existe, nada a remover: {diretorio}")
            return True
        
        shutil.rmtree(diretorio, ignore_errors=forcar)
        logger.info(f"Diretório removido: {diretorio}")
        return True
        
    except Exception as e:
        if forcar:
            logger.warning(f"Não foi possível remover completamente {diretorio}: {e}")
            return False
        else:
            logger.error(f"Erro ao remover diretório {diretorio}: {e}")
            return False

def verificar_diretorio_existe(diretorio: str) -> bool:
    """
    Verifica se um diretório existe.
    
    Args:
        diretorio: Caminho do diretório
        
    Returns:
        True se existe, False caso contrário
    """
    existe = os.path.exists(diretorio) and os.path.isdir(diretorio)
    logger.debug(f"Diretório {diretorio} existe: {existe}")
    return existe

def verificar_arquivo_existe(arquivo: str) -> bool:
    """
    Verifica se um arquivo existe.
    
    Args:
        arquivo: Caminho do arquivo
        
    Returns:
        True se existe, False caso contrário
    """
    existe = os.path.exists(arquivo) and os.path.isfile(arquivo)
    logger.debug(f"Arquivo {arquivo} existe: {existe}")
    return existe

def obter_tamanho_diretorio(diretorio: str) -> int:
    """
    Calcula o tamanho total de um diretório em bytes.
    
    Args:
        diretorio: Caminho do diretório
        
    Returns:
        Tamanho total em bytes
    """
    if not os.path.exists(diretorio):
        return 0
    
    tamanho_total = 0
    for dirpath, dirnames, filenames in os.walk(diretorio):
        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            if os.path.exists(filepath):
                tamanho_total += os.path.getsize(filepath)
    
    logger.debug(f"Tamanho do diretório {diretorio}: {tamanho_total} bytes")
    return tamanho_total

def formatar_tamanho(tamanho_bytes: int) -> str:
    """
    Formata tamanho em bytes para formato legível.
    
    Args:
        tamanho_bytes: Tamanho em bytes
        
    Returns:
        String formatada (ex: "1.5 MB")
    """
    for unidade in ['B', 'KB', 'MB', 'GB', 'TB']:
        if tamanho_bytes < 1024.0:
            return f"{tamanho_bytes:.2f} {unidade}"
        tamanho_bytes /= 1024.0
    return f"{tamanho_bytes:.2f} PB"