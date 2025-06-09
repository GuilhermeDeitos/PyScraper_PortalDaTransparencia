"""
Utilitários para manipulação e formatação de datas.
"""
import re
from datetime import datetime
from typing import Tuple, Dict

# Dicionário de meses em texto para números
dict_mes_numero = {
    1: "JANEIRO",
    2: "FEVEREIRO",
    3: "MARÇO",
    4: "ABRIL",
    5: "MAIO",
    6: "JUNHO",
    7: "JULHO",
    8: "AGOSTO",
    9: "SETEMBRO",
    10: "OUTUBRO",
    11: "NOVEMBRO",
    12: "DEZEMBRO"
}

# Dicionário inverso para converter de texto para número
dict_mes_texto_para_numero = {v: k for k, v in dict_mes_numero.items()}

def split_data(data_string: str) -> Tuple[int, int]:
    """
    Separa uma string de data no formato MM/AAAA em mês e ano.
    
    Args:
        data_string: String de data no formato MM/AAAA
        
    Returns:
        Tupla contendo (mes, ano) como inteiros
    """
    partes = data_string.split('/')
    if len(partes) != 2:
        raise ValueError(f"Formato de data inválido: {data_string}. Use MM/AAAA.")
    
    try:
        mes = int(partes[0])
        ano = int(partes[1])
        
        # Validações básicas
        if mes < 1 or mes > 12:
            raise ValueError(f"Mês inválido: {mes}. Deve estar entre 1 e 12.")
        if ano < 2002 or ano > 2023:
            raise ValueError(f"Ano fora do intervalo válido: {ano}. Deve estar entre 2002 e 2023.")
        
        return mes, ano
    except ValueError as e:
        raise ValueError(f"Erro ao converter data: {e}")

def data_valida(data_string: str) -> bool:
    """
    Verifica se uma string está no formato de data MM/AAAA.
    
    Args:
        data_string: String a ser validada
        
    Returns:
        True se a data estiver em formato válido, False caso contrário
    """
    # Verifica se segue o padrão MM/YYYY
    padrao = re.compile(r'^\d{2}/\d{4}$')
    if not padrao.match(data_string):
        return False
    
    # Verifica se a data é válida
    try:
        partes = data_string.split('/')
        mes = int(partes[0])
        ano = int(partes[1])
        
        # Tenta criar um objeto datetime (isso validará dias do mês, anos bissextos, etc.)
        datetime(year=ano, month=mes, day=1)  # Usamos o dia 1 para validar o mês e ano
        return True
    except (ValueError, IndexError):
        return False

def formatar_data_api(data_string: str) -> str:
    """
    Formata uma data para o formato aceito pela API.
    
    Args:
        data_string: Data no formato MM/AAAA
        
    Returns:
        Data formatada para a API
    """
    if not data_valida(data_string):
        raise ValueError(f"Formato de data inválido: {data_string}")
    
    partes = data_string.split('/')
    mes = partes[0]
    ano = partes[1]
    
    return f"{ano}-{mes}"

def formatar_periodo_texto(mes_inicio: int, ano_inicio: int, mes_fim: int, ano_fim: int) -> str:
    """
    Formata um período de consulta em texto legível.
    
    Args:
        mes_inicio: Mês inicial
        ano_inicio: Ano inicial
        mes_fim: Mês final
        ano_fim: Ano final
        
    Returns:
        String com período formatado
    """
    mes_inicio_texto = dict_mes_numero[mes_inicio]
    mes_fim_texto = dict_mes_numero[mes_fim]
    
    if ano_inicio == ano_fim:
        if mes_inicio == mes_fim:
            return f"{mes_inicio_texto}/{ano_inicio}"
        else:
            return f"{mes_inicio_texto} a {mes_fim_texto}/{ano_inicio}"
    else:
        return f"{mes_inicio_texto}/{ano_inicio} a {mes_fim_texto}/{ano_fim}"

def obter_mes_atual() -> int:
    """
    Retorna o mês atual.
    
    Returns:
        Número do mês atual (1-12)
    """
    return datetime.now().month

def obter_ano_atual() -> int:
    """
    Retorna o ano atual.
    
    Returns:
        Ano atual
    """
    return datetime.now().year