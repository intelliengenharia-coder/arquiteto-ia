#!/bin/bash
# ─── ARQUITETO IA — Setup Local ───────────────────────────────────────────────
# Execute: bash setup.sh

echo ""
echo "╔══════════════════════════════════════╗"
echo "║       ARQUITETO IA — Setup           ║"
echo "╚══════════════════════════════════════╝"
echo ""

# 1. Verifica Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 não encontrado. Instale em python.org"
    exit 1
fi
echo "✓ Python: $(python3 --version)"

# 2. Cria ambiente virtual
echo ""
echo "→ Criando ambiente virtual..."
python3 -m venv venv
source venv/bin/activate

# 3. Instala dependências
echo "→ Instalando dependências..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "✓ Dependências instaladas"

# 4. Verifica .env
if [ ! -f ".env" ]; then
    echo ""
    echo "⚠️  Arquivo .env não encontrado."
    echo "   Criando a partir do .env.example..."
    cp .env.example .env
    echo ""
    echo "┌─────────────────────────────────────────────────────┐"
    echo "│  AÇÃO NECESSÁRIA:                                   │"
    echo "│  Abra o arquivo .env e preencha suas chaves API:    │"
    echo "│                                                     │"
    echo "│  ANTHROPIC_API_KEY=sk-ant-...                       │"
    echo "│  REPLICATE_API_TOKEN=r8_...                         │"
    echo "│                                                     │"
    echo "│  Depois execute: bash run.sh                        │"
    echo "└─────────────────────────────────────────────────────┘"
else
    echo "✓ Arquivo .env encontrado"
    echo ""
    echo "→ Para iniciar o servidor execute:"
    echo "  bash run.sh"
fi

echo ""
echo "╔══════════════════════════════════════╗"
echo "║  Setup concluído!                    ║"
echo "╚══════════════════════════════════════╝"
