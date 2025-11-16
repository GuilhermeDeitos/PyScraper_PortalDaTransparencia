import re

def data_valida(data: str) -> bool:
    """Verifica se a data está no formato MM/YYYY."""
    try:
        mes, ano = map(int, data.split('/'))
        return 1 <= mes <= 12 and ano > 0
    except ValueError:
        return False
      
def split_data(data: str):
    """Divide a data em dia, mês e ano."""
    try:
        mes, ano = map(int, data.split('/'))
        return mes, ano
    except ValueError:
        raise ValueError("Formato de data inválido. Use MM/YYYY.")

def formatar_valor_monetario(valor: float) -> str:
    """Formata um valor float para o padrão monetário brasileiro."""
    sinal = '-' if valor < 0 else ''
    valor_abs = abs(valor)
    return f"{sinal}R$ {valor_abs:,.2f}".replace(',', 'X').replace('.', ',').replace('X', '.')

def extrair_numero(texto: str):
    """Extrai o primeiro número float de um texto."""
    # Remove espaços e símbolos de moeda
    texto_limpo = texto.replace('R$', '').replace(' ', '')
    
    # Regex para capturar números no formato brasileiro (1.000,50) ou internacional (1000.50)
    match = re.search(r'(\d{1,3}(?:\.\d{3})*,\d+|\d+\.\d+|\d+)', texto_limpo)
    
    if match:
        numero = match.group(1)
        # Converter formato brasileiro para internacional
        if ',' in numero:
            numero = numero.replace('.', '').replace(',', '.')
        try:
            return float(numero)
        except ValueError:
            return None
    return None

def limpar_texto(texto: str) -> str:
    """Remove espaços extras, quebras de linha e tabs do texto."""
    return ' '.join(texto.replace('\n', ' ').replace('\t', ' ').split())

def validar_range_valores(valor: float, minimo: float, maximo: float) -> bool:
    """Valida se o valor está dentro do intervalo [minimo, maximo]."""
    return minimo <= valor <= maximo

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