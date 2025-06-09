from fastapi import FastAPI
from app.Routes.routes import router as consulta
from app.Core.logging import configure_logging

# Configuração inicial
configure_logging()

# Criação da aplicação
app = FastAPI(
    title="API Crawler Transparência PR",
    description="API para consulta de dados do Portal da Transparência do Paraná",
    version="1.0.0"
)

# Registro de rotas
app.include_router(consulta, tags=["Consultas"])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)