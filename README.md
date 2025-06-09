# API Crawler Portal da Transparência PR

Um microsserviço para extração e consulta de dados do Portal da Transparência do Estado do Paraná, desenvolvido como parte de um Trabalho de Conclusão de Curso (TCC).

## Descrição

Este projeto implementa uma API RESTful que utiliza técnicas de web scraping para extrair dados de despesas públicas do Portal da Transparência do Paraná. O serviço permite consultas para períodos específicos e processa os dados para disponibilizá-los em formato JSON.

### Funcionalidades principais:

- Consulta de despesas por período (data inicial e final)
- Processamento assíncrono para consultas de múltiplos anos
- Acompanhamento do status de consultas em andamento
- Extração e normalização automática dos dados

## Instalação

### Pré-requisitos

- Python 3.11 ou superior
- Google Chrome ou Microsoft Edge instalado
- ChromeDriver compatível com a versão do seu navegador

### Configuração do ambiente

1. Clone o repositório:
   ```bash
   git clone <url-do-repositório>
   cd api_crawler
  ```
2. Crie e ative um ambiente virtual:
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac
```
3. Instale as dependências:
```bash
pip install -r requirements.txt
```
4. Baixe o chromedriver compatível com seu navegador:
   - Para Google Chrome, acesse: https://sites.google.com/chromium.org/driver/
   - Para Microsoft Edge, acesse: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/
Baixe o ChromeDriver compatível com seu navegador e coloque o executável na pasta raiz do projeto ou em um diretório no PATH.

## Estrutura do Projeto
```
api_crawler/
├── app/
│   ├── __init__.py
│   ├── main.py                  # Ponto de entrada da aplicação
│   ├── api/
│   │   ├── __init__.py
│   │   ├── routes/              # Endpoints da API
│   │   │   ├── __init__.py
│   │   │   └── consulta.py      
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py            # Configurações
│   │   └── logging.py           # Configuração de logs
│   ├── models/
│   │   ├── __init__.py
│   │   └── schema.py            # Modelos Pydantic
│   ├── services/
│   │   ├── __init__.py
│   │   ├── consulta_service.py  # Lógica de negócio
│   │   └── scraper_service.py   # Lógica de scraping
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── consulta_repo.py     # Gerenciamento de estado
│   └── utils/
│       ├── __init__.py
│       ├── browser_utils.py     # Utilitários de navegador
│       ├── date_utils.py        # Utilitários de data
│       ├── file_utils.py        # Utilitários de arquivo
│       ├── planilha.py          # Processamento das planilhas xls
│       └── validators.py        # Validações
├── logs/                        # Logs da aplicação
├── requirements.txt             # Dependências
└── README.md                    # Este arquivo
```

## Uso
``` bash
cd api_crawler
python -m app.main
```
Por padrão, a API estará disponível em http://localhost:8000.

## Em desenvolvimento