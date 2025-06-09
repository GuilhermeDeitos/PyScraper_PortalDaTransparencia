# app/schemas.py
from pydantic import BaseModel

class ConsultaParams(BaseModel):
    data_inicio: str  # formato: "MM/YYYY"
    data_fim: str     # formato: "MM/YYYY"

class RespostaEmProgresso(BaseModel):
    status: str = "em_andamento"
    mensagem: str
    id_consulta: str