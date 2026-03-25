# MCP Server

**Multi-LLM Gateway** para `mcp.observabilidadebrasil.org`

Um servidor MCP (Model Context Protocol) que atua como gateway inteligente para múltiplos backends LLM, com suporte a streaming, rate limiting, e monitoramento.

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    nginx (SSL + Rate Limit)                  │
│                  mcp.observabilidadebrasil.org               │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                     MCP Server (FastAPI)                     │
│                        Port 9200                             │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐        │
│  │ OpenAI  │  │ Claude  │  │ Ollama  │  │ Custom  │        │
│  │ Provider│  │ Provider│  │ Provider│  │ Provider│        │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘        │
│       │            │            │            │              │
│       └────────────┴────────────┴────────────┘              │
│                         │                                    │
│              ┌──────────▼──────────┐                        │
│              │   LLM Router        │                        │
│              │ (load balance,      │                        │
│              │  fallback, routing) │                        │
│              └─────────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

## 🚀 Features

- **Multi-LLM Backend**: Suporte a OpenAI, Anthropic Claude, Ollama (local), e providers customizados
- **Streaming SSE**: Respostas em tempo real via Server-Sent Events
- **Rate Limiting**: Proteção contra abuso (nginx + aplicação)
- **Fallback Automático**: Se um provider falhar, tenta o próximo
- **Monitoramento**: Dashboard separado de requests, métodos, e abuse
- **Health Checks**: Endpoints de saúde para cada provider
- **Docker Ready**: Deploy simplificado com Docker Compose

## 📦 Instalação

### Requisitos

- Python 3.11+
- nginx (para produção)
- Docker (opcional)

### Desenvolvimento Local

```bash
# Clonar repositório
git clone https://github.com/tgosoul2019/mcp.git
cd mcp

# Criar virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Instalar dependências
pip install -e ".[dev]"

# Configurar variáveis de ambiente
cp .env.example .env
# Editar .env com suas API keys

# Rodar servidor
python -m mcp_server
```

### Produção (VPS)

```bash
# No servidor
cd /dados
git clone https://github.com/tgosoul2019/mcp.git
cd mcp

# Setup
./scripts/setup.sh

# Iniciar serviço
sudo systemctl start mcp-server
```

## ⚙️ Configuração

### Variáveis de Ambiente

```bash
# Server
MCP_HOST=127.0.0.1
MCP_PORT=9200
MCP_DEBUG=false

# LLM Providers (configure apenas os que usar)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
OLLAMA_BASE_URL=http://localhost:11434

# Default Provider
MCP_DEFAULT_PROVIDER=openai

# Rate Limiting (aplicação)
MCP_RATE_LIMIT_REQUESTS=100
MCP_RATE_LIMIT_WINDOW=60

# Logging
MCP_LOG_LEVEL=INFO
MCP_LOG_FILE=/var/log/mcp/mcp.log
```

## 🔌 API Endpoints

### Chat Completion

```bash
POST /v1/chat/completions
Content-Type: application/json

{
  "model": "gpt-4",
  "messages": [
    {"role": "user", "content": "Hello!"}
  ],
  "stream": true,
  "provider": "openai"  # opcional, usa default se omitido
}
```

### Health Check

```bash
GET /health
GET /health/providers
```

### Metrics

```bash
GET /metrics
```

## 📊 Monitoramento

O MCP tem seu próprio dashboard de monitoramento separado do KCP:

- **URL**: `https://mcp.observabilidadebrasil.org/admin/monitor`
- Requests por provider
- Latência média
- Taxa de erros
- IPs mais ativos
- Abuse detection

## 🐳 Docker

```bash
# Build
docker build -t mcp-server .

# Run
docker run -d \
  --name mcp-server \
  -p 9200:9200 \
  -e OPENAI_API_KEY=sk-... \
  mcp-server
```

## 📁 Estrutura do Projeto

```
mcp/
├── mcp_server/
│   ├── __init__.py
│   ├── __main__.py
│   ├── app.py              # FastAPI app
│   ├── config.py           # Configurações
│   ├── router.py           # LLM Router
│   ├── providers/
│   │   ├── __init__.py
│   │   ├── base.py         # Abstract Provider
│   │   ├── openai.py
│   │   ├── anthropic.py
│   │   └── ollama.py
│   ├── middleware/
│   │   ├── __init__.py
│   │   ├── rate_limit.py
│   │   └── logging.py
│   └── monitor/
│       ├── __init__.py
│       ├── collector.py    # Métricas
│       └── dashboard.py    # UI
├── infra/
│   ├── nginx/
│   │   └── mcp.conf
│   ├── systemd/
│   │   └── mcp-server.service
│   └── docker/
│       ├── Dockerfile
│       └── docker-compose.yml
├── scripts/
│   ├── setup.sh
│   └── deploy.sh
├── tests/
├── pyproject.toml
├── .env.example
└── README.md
```

## 📄 Licença

MIT

## 🔗 Links

- **Produção**: https://mcp.observabilidadebrasil.org
- **Repositório**: https://github.com/tgosoul2019/mcp
