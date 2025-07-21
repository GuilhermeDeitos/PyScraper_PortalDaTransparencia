
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
