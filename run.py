#!/usr/bin/env python3
"""
Script de inicialização para o PyScraper Portal da Transparência
Execute este arquivo para iniciar a API
"""

import sys
import os

# Adiciona o diretório raiz do projeto ao Python path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

if __name__ == "__main__":
    from app.main import app
    import uvicorn
    
    uvicorn.run(
        "app.main:app", 
        host="0.0.0.0", 
        port=8001, 
        reload=False
    )
