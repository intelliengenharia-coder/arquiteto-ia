#!/bin/bash
# ─── ARQUITETO IA — Iniciar Servidor ─────────────────────────────────────────

# Ativa ambiente virtual
source venv/bin/activate 2>/dev/null || true

# Carrega variáveis de ambiente
export $(cat .env | grep -v '^#' | xargs) 2>/dev/null

# Verifica chaves
if [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "❌ ANTHROPIC_API_KEY não definida no .env"
    exit 1
fi

echo ""
echo "╔══════════════════════════════════════════════════╗"
echo "║  ARQUITETO IA — Servidor iniciando...            ║"
echo "║                                                  ║"
echo "║  API local:  http://localhost:8000               ║"
echo "║  Docs:       http://localhost:8000/docs          ║"
echo "║                                                  ║"
echo "║  Ctrl+C para parar                               ║"
echo "╚══════════════════════════════════════════════════╝"
echo ""

uvicorn main:app --reload --host 0.0.0.0 --port 8000
