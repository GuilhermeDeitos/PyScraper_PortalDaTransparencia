"""
Funções de validação para parâmetros de entrada.
"""
import logging
from typing import Tuple
from app.utils.date_utils import data_valida, split_data

logger = logging.getLogger(__name__)

def validar_parametros(data_inicio: str, data_fim: str) -> Tuple[int, int, int, int]:
    """
    Valida os parâmetros de entrada e retorna mês e ano de início e fim.
    
    Args:
        data_inicio: Data inicial no formato MM/YYYY
        data_fim: Data final no formato MM/YYYY
        
    Returns:
        Tupla contendo (mes_inicio, ano_inicio, mes_fim, ano_fim)
        
    Raises:
        ValueError: Se os parâmetros forem inválidos
    """
    # Verifica se os campos obrigatórios estão presentes
    if not data_inicio or not data_fim:
        logger.error("Campos de data obrigatórios ausentes")
        raise ValueError("Os campos data_inicio e data_fim são obrigatórios.")
    
    # Verifica formato das datas
    if not data_valida(data_inicio) or not data_valida(data_fim):
        logger.error(f"Formato de data inválido: inicio={data_inicio}, fim={data_fim}")
        raise ValueError("Formato de data inválido. Use MM/YYYY.")
    
    # Extrai mês e ano
    mes_inicio, ano_inicio = split_data(data_inicio)
    mes_fim, ano_fim = split_data(data_fim)
    
    # Verifica se data início <= data fim
    if (ano_inicio > ano_fim) or (ano_inicio == ano_fim and mes_inicio > mes_fim):
        logger.error(f"Período inválido: inicio={data_inicio}, fim={data_fim}")
        raise ValueError("A data de início não pode ser maior que a data de fim.")
    
    
    logger.debug(f"Parâmetros validados: mes_inicio={mes_inicio}, ano_inicio={ano_inicio}, "
                f"mes_fim={mes_fim}, ano_fim={ano_fim}")
    
    return mes_inicio, ano_inicio, mes_fim, ano_fim

def validar_id_consulta(id_consulta: str) -> bool:
    """
    Valida se um ID de consulta está em formato válido.
    
    Args:
        id_consulta: ID da consulta a ser validado
        
    Returns:
        True se o ID for válido, False caso contrário
    """
    import re
    # Valida formato UUID
    uuid_pattern = re.compile(r'^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
    return bool(uuid_pattern.match(id_consulta.lower()))