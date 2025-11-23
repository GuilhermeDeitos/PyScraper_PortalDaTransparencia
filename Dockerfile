# Dockerfile do API Scraper: Nova Seção RUN para Chrome

FROM python:3.11-slim

# Instalar Chrome e dependências para Selenium/Playwright
RUN apt-get update && apt-get install -y \
    wget gnupg unzip curl ca-certificates lsb-release \
    # Dependências de sistema para o Chrome rodar em Headless:
    libnss3 libfontconfig \
    && \
    # 1. Baixar a chave GPG para um arquivo temporário no sistema de arquivos do container
    curl -fsSL https://dl.google.com/linux/linux_signing_key.pub -o /tmp/google-chrome.key \
    && \
    # 2. Processar a chave DO ARQUIVO temporário e salvá-la em keyrings
    gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg /tmp/google-chrome.key \
    && \
    # 3. Adicionar o repositório Google Chrome, referenciando a chave recém-adicionada
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/google-chrome.gpg] http://dl.google.com/linux/chrome/deb/ stable main" | tee /etc/apt/sources.list.d/google-chrome.list > /dev/null \
    && \
    # 4. Instalar o Chrome e limpar
    apt-get update \
    && apt-get install -y google-chrome-stable \
    && rm -rf /var/lib/apt/lists/* /tmp/google-chrome.key

WORKDIR /app

# 1. COPIAR requirements.txt ANTES de instalar para aproveitar o cache! (CORREÇÃO)
COPY requirements.txt .

# 2. Instalação das dependências Python
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar o restante do código (MUITO mais rápido, pois usa o cache da camada 2)
COPY . .

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8001/system-status || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]