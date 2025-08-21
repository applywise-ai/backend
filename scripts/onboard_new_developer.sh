#!/bin/bash

# New Developer Onboarding Script
# Sets up database access via Tailscale

echo "🚀 ApplyWise Developer Onboarding"
echo "=================================="
echo "Prerequisites: Tailscale infrastructure is already set up"
echo "You just need to connect to the existing network"
echo ""

# Check if Tailscale is installed
if ! command -v tailscale &> /dev/null; then
    echo "📱 Installing Tailscale..."
    if [[ "$OSTYPE" == "darwin"* ]]; then
        brew install --cask tailscale
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        curl -fsSL https://tailscale.com/install.sh | sh
    else
        echo "❌ Please install Tailscale manually: https://tailscale.com/download"
        exit 1
    fi
    echo "✅ Tailscale installed!"
else
    echo "✅ Tailscale already installed"
fi

# Check Tailscale status
echo ""
echo "🔍 Checking Tailscale connection..."
if tailscale status &>/dev/null; then
    echo "✅ Tailscale is connected"
    tailscale status
else
    echo "⚠️ Tailscale not connected. Please:"
    echo "1. Start Tailscale app"
    echo "2. Sign in with your account"
    echo "3. Get added to the ApplyWise Tailscale network"
    echo "4. Re-run this script"
    exit 1
fi

# Test database connectivity
echo ""
echo "🔍 Testing database connectivity..."
if nc -z -v 172.31.85.170 5432 2>/dev/null; then
    echo "✅ Database is reachable via Tailscale!"
else
    echo "❌ Database not reachable. Please ensure:"
    echo "1. You're connected to Tailscale"
    echo "2. You have access to the ApplyWise network"
    echo "3. Contact admin to verify subnet routes are enabled"
    exit 1
fi

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "📝 Creating .env file..."
    
    read -p "Supabase URL: " SUPABASE_URL
    read -p "Supabase Service Role Key: " SUPABASE_KEY
    read -p "Supabase DB Password: " -s SUPABASE_DB_PASSWORD
    echo
    read -p "Upstash Redis URL with token (e.g., rediss://:your-token@your-instance.upstash.io:6379): " REDIS_URL
    
    cat > .env << EOF
# Supabase Configuration
SUPABASE_URL=$SUPABASE_URL
SUPABASE_KEY=$SUPABASE_KEY
SUPABASE_DB_PASSWORD=$SUPABASE_DB_PASSWORD

# Redis Configuration (Upstash)
REDIS_URL=$REDIS_URL
# CELERY_BROKER_URL and CELERY_RESULT_BACKEND use REDIS_URL

# Application Configuration
DEBUG=true
ENVIRONMENT=development
HEADLESS_BROWSER=true
BROWSER_TIMEOUT=10

# CORS Configuration
CORS_ORIGINS=http://localhost:3000

# Add other environment variables as needed
# FIREBASE_CREDENTIALS=
# FIREBASE_STORAGE_BUCKET=

EOF

    echo "✅ .env file created!"
else
    echo "⚠️ .env file already exists, skipping creation"
fi

# Test database connection
echo ""
echo "🧪 Testing database connection..."
if command -v python &> /dev/null && [ -f scripts/check_db_connection.py ]; then
    python scripts/check_db_connection.py
else
    echo "⚠️ Python or check script not found, manual test:"
    echo "Run: make check-db"
fi

echo ""
echo "🎉 Onboarding complete!"
echo ""
echo "📋 Next steps:"
echo "1. Install dependencies: make install"
echo "2. Start development: make dev"
echo "3. Start Celery worker: make celery"
echo ""
echo "🔧 Useful commands:"
echo "  make help        - Show all available commands"
echo "  make check-db    - Test database connection"
echo "  make dev         - Start development server"
echo "  make celery      - Start Celery worker"
echo ""
echo "📚 Documentation:"
echo "  - Tailscale admin: https://login.tailscale.com/admin"
echo "  - API docs: http://localhost:8000/docs (after starting server)" 