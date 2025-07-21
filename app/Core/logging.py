import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from datetime import datetime

def configure_logging():
    """
    Configura o sistema de logging da aplicação.
    - Logs de nível INFO e acima vão para o console
    - Todos os logs vão para arquivo com rotação
    - Formato personalizado com timestamp, nível, módulo e mensagem
    """
    # Cria diretório de logs se não existir
    log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # Define formato para mensagens de log
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    formatter = logging.Formatter(log_format)
    
    # Configura logger root
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Handler para console (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    
    # Handler para arquivo com rotação
    # Cria um novo arquivo a cada 5MB, mantém até 10 arquivos de backup
    log_file = os.path.join(log_dir, f'api_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5*1024*1024, backupCount=10, encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # Nível mais detalhado para arquivo
    file_handler.setFormatter(formatter)
    
    # Adiciona os handlers ao logger root
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)
    
    # Configura loggers específicos de módulos
    configure_module_loggers()
    
    # Reduz nível de log de bibliotecas de terceiros
    configure_third_party_loggers()
    
    logging.info("Sistema de logging configurado")

def configure_module_loggers():
    """
    Configura níveis de log específicos para módulos da aplicação.
    Permite controle mais granular sobre o que é logado.
    """
    # Configura logger para módulos da aplicação com nível DEBUG
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.DEBUG)
    
    # Configurações específicas para submódulos
    logging.getLogger("app.services.scraper_service").setLevel(logging.DEBUG)

def configure_third_party_loggers():
    """
    Reduz o nível de log de bibliotecas de terceiros para evitar 
    poluição nos logs com mensagens não relevantes.
    """
    # Reduz verbosidade de bibliotecas comuns
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("selenium").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("fastapi").setLevel(logging.WARNING)

# Função auxiliar para obter logger de um módulo
def get_logger(name):
    """
    Obtém um logger configurado para um módulo específico.
    
    Args:
        name: Nome do módulo ou caminho completo
        
    Returns:
        Logger configurado
    """
    return logging.getLogger(name)