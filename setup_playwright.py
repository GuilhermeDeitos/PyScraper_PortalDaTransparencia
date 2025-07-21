#!/usr/bin/env python3
"""
Script para instalar e configurar o Playwright
Execute este script após instalar as dependências Python
"""

import subprocess
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def instalar_playwright():
    """Instala o Playwright e seus browsers"""
    try:
        logger.info("Instalando Playwright...")
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"], check=True)
        
        logger.info("Instalando browsers do Playwright...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        
        logger.info("Playwright instalado com sucesso!")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Erro ao instalar Playwright: {e}")
        return False
    except Exception as e:
        logger.error(f"Erro inesperado: {e}")
        return False

if __name__ == "__main__":
    if instalar_playwright():
        print("✅ Playwright configurado com sucesso!")
        print("Agora você pode usar as rotas /consultar-playwright")
    else:
        print("❌ Falha na configuração do Playwright")
        sys.exit(1)
