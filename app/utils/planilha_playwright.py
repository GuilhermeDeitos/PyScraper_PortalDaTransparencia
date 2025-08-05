import asyncio
import os
import time
import pandas as pd
import numpy as np
import logging
from typing import List, Dict, Any, Optional
from pathlib import Path
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from app.utils.file_utils import (
    obter_arquivos_mais_recentes, 
    limpar_diretorio
)

logger = logging.getLogger(__name__)
async def baixar_e_processar_planilha_playwright(page: Page, download_dir: str) -> Optional[List[Dict[str, Any]]]:
    """
    Baixa e processa a planilha de dados usando Playwright com API nativa de downloads.
    
    Args:
        page: Objeto Page do Playwright
        download_dir: Diretório para salvar downloads
        
    Returns:
        Lista de dicionários com os dados da planilha ou None em caso de erro
    """
    logger.info(f"=== INÍCIO DA FUNÇÃO DOWNLOAD PLAYWRIGHT ===")
    logger.info(f"Diretório de download configurado: {download_dir}")
    
    try:
        # Limpa quaisquer arquivos antigos para evitar confusão
        logger.info("Iniciando limpeza do diretório de download...")
        await asyncio.get_event_loop().run_in_executor(None, limpar_diretorio, download_dir)
        logger.info(f"Diretório de download limpo: {download_dir}")
        
        # Aguarda a página carregar completamente
        logger.info("Aguardando página carregar...")
        await page.wait_for_load_state('networkidle')
        
        # Aguarda especificamente pelos componentes PrimeFaces carregarem
        try:
            await page.wait_for_function("window.PrimeFaces !== undefined", timeout=10000)
            logger.info("PrimeFaces carregado com sucesso")
        except Exception as e:
            logger.warning(f"PrimeFaces pode não ter carregado completamente: {e}")

        # Aguarda o botão aparecer e estar habilitado
        logger.info("Aguardando botão de download aparecer...")
        await page.wait_for_selector("button[id='formPesquisa:btnVisualizarPlanilha']", 
                                   state='visible', timeout=15000)
        
        logger.info("Botão encontrado, verificando se está habilitado...")
        is_enabled = await page.is_enabled("button[id='formPesquisa:btnVisualizarPlanilha']")
        logger.info(f"Botão habilitado: {is_enabled}")
        
        if not is_enabled:
            logger.error("Botão de download não está habilitado")
            return None

        logger.info("Iniciando processo de download...")
        
        async with page.expect_download(timeout=60000) as download_info:
            # Clica no botão para iniciar o download
            await page.click("button[id='formPesquisa:btnVisualizarPlanilha']")
            logger.info("Clique no botão de download realizado")
        
        # Aguarda o download completar
        download = await download_info.value
        logger.info(f"Download capturado: {download.suggested_filename}")
        
        # Define o caminho para salvar o arquivo
        arquivo_destino = os.path.join(download_dir, download.suggested_filename)
        logger.info(f"Salvando arquivo em: {arquivo_destino}")
        
        # Salva o arquivo no diretório especificado
        await download.save_as(arquivo_destino)
        logger.info(f"Arquivo salvo com sucesso")
        
        # Verifica se o arquivo foi salvo corretamente
        if not os.path.exists(arquivo_destino):
            logger.error(f"Arquivo não foi encontrado após download: {arquivo_destino}")
            return None
        
        tamanho_arquivo = os.path.getsize(arquivo_destino)
        logger.info(f"Arquivo salvo - Tamanho: {tamanho_arquivo} bytes")
        
        if tamanho_arquivo == 0:
            logger.error("Arquivo baixado está vazio")
            return None
        
        logger.info("Download concluído com sucesso, iniciando processamento...")
        
        # LOGS DETALHADOS ANTES DO PROCESSAMENTO
        logger.info("=== INICIANDO PROCESSAMENTO DA PLANILHA ===")
        logger.info(f"Arquivo a ser processado: {arquivo_destino}")
        logger.info(f"Arquivo existe: {os.path.exists(arquivo_destino)}")
        logger.info(f"Tamanho do arquivo: {tamanho_arquivo} bytes")
        
        # Processa a planilha em uma thread separada para não bloquear
        logger.info("Executando processamento em thread separada...")
        registros = await asyncio.get_event_loop().run_in_executor(
            None, _processar_planilha_sync, arquivo_destino
        )
        
        logger.info(f"Processamento concluído - Resultado: {type(registros)}")
        
        if registros is None:
            logger.error("Processamento retornou None")
            return None
        
        logger.info(f"=== FIM DA FUNÇÃO - {len(registros)} registros processados ===")
        return registros
        
    except Exception as e:
        logger.error(f"Erro geral na função de download: {e}", exc_info=True)
        
        # Tira screenshot para debug em caso de erro
        try:
            screenshot_path = os.path.join(download_dir, "debug_download_error.png")
            await page.screenshot(path=screenshot_path, full_page=True)
            logger.info(f"Screenshot de erro salvo em: {screenshot_path}")
        except Exception as screenshot_error:
            logger.error(f"Erro ao tirar screenshot: {screenshot_error}")
        
        return None

def _processar_planilha_sync(arquivo_baixado: str) -> Optional[List[Dict[str, Any]]]:
    """
    Processa a planilha de forma síncrona (executada em thread separada).
    
    Args:
        arquivo_baixado: Caminho para o arquivo baixado
        
    Returns:
        Lista de dicionários com os dados processados, ou None em caso de erro
    """
    logger.info(f"=== INICIO _processar_planilha_sync ===")
    logger.info(f"Arquivo recebido: {arquivo_baixado}")
    
    try:
        # Verificações iniciais
        if not os.path.exists(arquivo_baixado):
            logger.error(f"Arquivo não encontrado: {arquivo_baixado}")
            return None
        
        tamanho = os.path.getsize(arquivo_baixado)
        logger.info(f"Tamanho do arquivo: {tamanho} bytes")
        
        if tamanho == 0:
            logger.error("Arquivo está vazio")
            return None
        
        # Leitura do arquivo Excel
        logger.info("Tentando ler arquivo Excel...")
        df = None
        
        try:
            # Tenta ler com xlrd (compatível com formatos .xls antigos)
            logger.info("Tentando com engine 'xlrd'...")
            df = pd.read_excel(arquivo_baixado, engine='xlrd')
            logger.info("Arquivo lido com sucesso usando 'xlrd'")
        except Exception as e1:
            logger.warning(f"Erro ao processar com xlrd: {e1}")
            try:
                # Tenta com openpyxl (para formatos .xlsx mais recentes)
                logger.info("Tentando com engine 'openpyxl'...")
                df = pd.read_excel(arquivo_baixado, engine='openpyxl')
                logger.info("Arquivo lido com sucesso usando 'openpyxl'")
            except Exception as e2:
                logger.error(f"Falha ao processar arquivo com openpyxl: {e2}")
                raise
        
        if df is None:
            logger.error("DataFrame não foi criado")
            return None
        
        logger.info(f"DataFrame criado - Shape inicial: {df.shape}")
        logger.info(f"Colunas iniciais: {list(df.columns)}")
        
        # Normalização e limpeza dos dados
        logger.info("Iniciando normalização e limpeza dos dados...")
        
        # Remove colunas completamente vazias
        colunas_antes = len(df.columns)
        df = df.dropna(axis=1, how='all')
        colunas_depois = len(df.columns)
        logger.info(f"Colunas vazias removidas: {colunas_antes} -> {colunas_depois}")
        
        # Renomeia colunas para formato mais amigável
        logger.info("Renomeando colunas...")
        df.columns = [
            str(col).strip().lower().replace(' ', '_').replace('/', '_').replace('-', '_')
            for col in df.columns
        ]
        logger.info(f"Colunas renomeadas: {list(df.columns)}")
        
        logger.info("Aplicando correção de colunas...")
        df = corrigir_colunas_playwright(df)
        logger.info(f"Colunas após correção: {list(df.columns)}")
        logger.info(f"Shape após correção de colunas: {df.shape}")
        
        # Remove primeira linha se existir (cabeçalhos duplicados)
        if len(df) > 0:
            logger.info("Removendo primeira linha (cabeçalho duplicado)")
            df = df.drop(0)
            logger.info(f"Shape após remover primeira linha: {df.shape}")
        
        # Substitui valores não compatíveis com JSON
        logger.info("Substituindo valores incompatíveis...")
        df = df.replace([float('inf'), float('-inf'), pd.NA, pd.NaT], np.nan)
        
        # Aplicar filtros específicos
        registros_antes_filtro = len(df)
        logger.info(f"Registros antes do filtro: {registros_antes_filtro}")
        
        # Retirar os dados cuja unidade orçamentária é tecpar, gestão e fundo paraná
        if 'UNIDADE_ORÇAMENTÁRIA' in df.columns:
            logger.info("Aplicando filtro da unidade orçamentária...")
            filtro_antes = len(df)
            df = df[~df['UNIDADE_ORÇAMENTÁRIA'].str.contains(
                "45.70 - SECRETARIA DE ESTADO DA CIÊNCIA, TECNOLO / INSTITUTO DE TECNOLOGIA DO PARANÁ – TECPAR|"
                "45.04 - SECRETARIA DE ESTADO DA CIÊNCIA, TECNOLO / GESTÃO ADMINISTRATIVA|"
                "45.60 - SECRETARIA DE ESTADO DA CIÊNCIA, TECNOLO / FUNDO PARANÁ", 
                na=False
            )]
            filtro_depois = len(df)
            logger.info(f"Filtro aplicado: {filtro_antes} -> {filtro_depois} registros")
        else:
            logger.warning("Coluna 'UNIDADE_ORÇAMENTÁRIA' não encontrada - filtro não aplicado")
            logger.info(f"Colunas disponíveis: {list(df.columns)}")
        
        # Converte para lista de dicionários
        logger.info("Convertendo para lista de dicionários...")
        registros = df.to_dict(orient='records')
        logger.info(f"Conversão concluída: {len(registros)} registros")
        
        # Limpeza final para compatibilidade com JSON
        logger.info("Aplicando limpeza final para compatibilidade JSON...")
        for i, registro in enumerate(registros):
            for chave, valor in list(registro.items()):
                # Trata valores NaN/None
                if isinstance(valor, float) and (np.isnan(valor) or np.isinf(valor)):
                    registro[chave] = None
                # Converte valores numpy para tipos Python nativos
                elif hasattr(valor, 'dtype') and isinstance(valor, np.generic):
                    registro[chave] = valor.item()
            
            if i == 0:  # Log do primeiro registro como exemplo
                logger.info(f"Exemplo do primeiro registro: {dict(list(registro.items())[:3])}")
        
        logger.info(f"Processamento concluído com sucesso: {len(registros)} registros finais")
        
        # Tenta excluir o arquivo após processamento
        try:
            os.remove(arquivo_baixado)
            logger.info(f"Arquivo temporário excluído: {os.path.basename(arquivo_baixado)}")
        except Exception as e:
            logger.warning(f"Não foi possível excluir o arquivo: {e}")
        
        logger.info(f"=== FIM _processar_planilha_sync - SUCESSO ===")
        return registros
        
    except Exception as e:
        logger.error(f"=== ERRO em _processar_planilha_sync: {e} ===", exc_info=True)
        return None


def corrigir_colunas_playwright(df):
    """
    Corrige nomes de colunas tratando subheaders:
    - Substitui colunas "unnamed" com subheader "NO MÊS" pelo nome da coluna anterior + "_no_mes"
    - Adiciona "_ate_mes" nas colunas com subheader "ATÉ MÊS"
    - Converte todos os nomes para maiúsculas
    """
    nova_estrutura = {}
    coluna_anterior = None
    
    # Primeiro, extrair os nomes das colunas e seus valores de subheader
    colunas = df.columns.tolist()
    subheaders = df.iloc[0].tolist() if len(df) > 0 else [None] * len(colunas)
    
    # Mapear para o novo formato
    for i, (coluna, subheader) in enumerate(zip(colunas, subheaders)):
        # Verificar se é uma coluna unnamed
        if 'unnamed' in str(coluna).lower():
            novo_nome = f"{coluna_anterior}_no_mes"
            nova_estrutura[coluna] = novo_nome
        else:
            # Tratamento especial para a coluna "pago_(r$)"
            if "pago_(r$)" in str(coluna).lower() and "no_mes" not in str(coluna).lower():
                novo_nome = f"{coluna}_ate_mes"
                nova_estrutura[coluna] = novo_nome
            # Para colunas nomeadas com "ATÉ MÊS", adicionar sufixo
            elif isinstance(subheader, str) and subheader == 'ATÉ MÊS':
                novo_nome = f"{coluna}_ate_mes"
                nova_estrutura[coluna] = novo_nome
            else:
                nova_estrutura[coluna] = coluna
            
            # Armazenar nome da coluna para uso com unnamed seguintes
            coluna_anterior = coluna
    
    # Renomear colunas no DataFrame
    df = df.rename(columns=nova_estrutura)
    
    # Converter todos os nomes para maiúsculas
    df.columns = [str(col).upper() for col in df.columns]
    
    return df

async def processar_planilha_excel_async(file_path: str) -> Optional[List[Dict[str, Any]]]:
    """
    Processa um arquivo Excel de forma assíncrona.
    
    Args:
        file_path: Caminho para o arquivo Excel
        
    Returns:
        Lista de dicionários com os dados processados
    """
    try:
        logger.info(f"Processando arquivo Excel: {file_path}")
        
        # Executa o processamento em uma thread separada para não bloquear
        loop = asyncio.get_event_loop()
        dados = await loop.run_in_executor(None, _processar_planilha_sync, file_path)
        
        logger.info(f"Processamento concluído: {len(dados) if dados else 0} registros")
        return dados
        
    except Exception as e:
        logger.error(f"Erro ao processar planilha Excel: {e}")
        return None
