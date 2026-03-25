#!/bin/bash
# ══════════════════════════════════════════════════════════════════════════════
# MCP Server — Setup Script
# Run on server: ./scripts/setup.sh
# ══════════════════════════════════════════════════════════════════════════════

set -e

echo "════════════════════════════════════════════════════════════"
echo "  MCP Server Setup"
echo "════════════════════════════════════════════════════════════"

# ── Check we're in the right directory ────────────────────────────────────────
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Run this script from the mcp repository root"
    exit 1
fi

MCP_DIR=$(pwd)
echo "📁 MCP directory: $MCP_DIR"

# ── Create mcp user if not exists ─────────────────────────────────────────────
if ! id -u mcp &>/dev/null; then
    echo "👤 Creating mcp user..."
    sudo useradd -r -s /bin/false -d /dados/mcp mcp
fi

# ── Create log directory ──────────────────────────────────────────────────────
echo "📁 Creating log directory..."
sudo mkdir -p /var/log/mcp
sudo chown mcp:mcp /var/log/mcp

# ── Create Python virtual environment ─────────────────────────────────────────
echo "🐍 Creating virtual environment..."
python3 -m venv .venv
source .venv/bin/activate

# ── Install dependencies ──────────────────────────────────────────────────────
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -e ".[dev]"

# ── Copy environment file ─────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "⚙️  Creating .env file..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your API keys!"
fi

# ── Install systemd service ───────────────────────────────────────────────────
echo "🔧 Installing systemd service..."
sudo cp infra/systemd/mcp-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable mcp-server

# ── Install nginx config ──────────────────────────────────────────────────────
echo "🌐 Installing nginx configuration..."
sudo cp infra/nginx/mcp.conf /etc/nginx/sites-available/mcp
sudo ln -sf /etc/nginx/sites-available/mcp /etc/nginx/sites-enabled/

# Check if SSL cert exists
if [ ! -f "/etc/letsencrypt/live/mcp.observabilidadebrasil.org/fullchain.pem" ]; then
    echo "⚠️  SSL certificate not found!"
    echo "   Run: sudo certbot --nginx -d mcp.observabilidadebrasil.org"
    echo "   Then: sudo systemctl reload nginx"
else
    sudo nginx -t && sudo systemctl reload nginx
fi

# ── Create htpasswd for admin ─────────────────────────────────────────────────
if [ ! -f "/etc/nginx/.mcp-htpasswd" ]; then
    echo "🔐 Creating admin htpasswd..."
    echo "   Default: admin / changeme"
    echo 'admin:$apr1$xyz$hashed_password' | sudo tee /etc/nginx/.mcp-htpasswd > /dev/null
    echo "⚠️  Please update /etc/nginx/.mcp-htpasswd with a real password!"
    echo "   Use: htpasswd -c /etc/nginx/.mcp-htpasswd admin"
fi

# ── Set permissions ───────────────────────────────────────────────────────────
echo "🔒 Setting permissions..."
sudo chown -R mcp:mcp "$MCP_DIR"
sudo chmod 600 "$MCP_DIR/.env"

echo ""
echo "════════════════════════════════════════════════════════════"
echo "  ✅ Setup complete!"
echo "════════════════════════════════════════════════════════════"
echo ""
echo "  Next steps:"
echo "    1. Edit .env with your API keys"
echo "    2. Get SSL certificate (if not done):"
echo "       sudo certbot --nginx -d mcp.observabilidadebrasil.org"
echo "    3. Start the service:"
echo "       sudo systemctl start mcp-server"
echo "    4. Check status:"
echo "       sudo systemctl status mcp-server"
echo "       curl https://mcp.observabilidadebrasil.org/health"
echo ""
