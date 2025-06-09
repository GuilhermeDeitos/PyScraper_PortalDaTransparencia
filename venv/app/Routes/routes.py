from fastapi import APIRouter, Response, status, BackgroundTasks
from app.Models.Schema import ConsultaParams
from app.Services.consulta_service import ConsultaService
import logging

logger = logging.getLogger(__name__)
router = APIRouter()
consulta_service = ConsultaService()

@router.post("/consultar", 
            summary="Consulta dados do Portal da Transparência",
            response_description="Dados de despesas do período solicitado")
async def consultar(body: ConsultaParams, response: Response, background_tasks: BackgroundTasks):
    try:
        resultado = await consulta_service.processar_consulta(body, background_tasks)
        
        # Define status code baseado no tipo de resultado
        if "id_consulta" in resultado:
            response.status_code = status.HTTP_202_ACCEPTED
        else:
            response.status_code = status.HTTP_200_OK
        
        return resultado
    except ValueError as e:
        logger.error(f"Erro de validação: {str(e)}")
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"error": str(e)}
    except Exception as e:
        logger.error(f"Erro interno: {str(e)}", exc_info=True)
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        return {"error": f"Erro interno: {str(e)}"}

@router.get("/status-consulta/{id_consulta}", 
           summary="Verifica o status de uma consulta em andamento")
async def verificar_status_consulta(id_consulta: str, response: Response):
    resultado = consulta_service.obter_status_consulta(id_consulta)
    
    if "error" in resultado:
        response.status_code = status.HTTP_404_NOT_FOUND
    elif resultado.get("status") == "concluido":
        response.status_code = status.HTTP_200_OK
    elif resultado.get("status") == "erro":
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    else:
        response.status_code = status.HTTP_202_ACCEPTED
    
    return resultado