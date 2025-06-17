#!/bin/bash
echo "📱 Installing Tailscale on your local machine..."

if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    if ! command -v tailscale &> /dev/null; then
        echo "Installing Tailscale via Homebrew..."
        brew install --cask tailscale
        echo "✅ Tailscale installed. Please start it from Applications or System Preferences"
    else
        echo "✅ Tailscale already installed"
    fi
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
    # Linux
    curl -fsSL https://tailscale.com/install.sh | sh
    echo "Run: sudo tailscale up"
else
    echo "Please install Tailscale manually from https://tailscale.com/download"
fi

echo ""
echo "🎯 Next steps:"
echo "1. Start Tailscale on your machine"
echo "2. Sign up/login to Tailscale"
echo "3. Connect to gateway: ./connect_tailscale_gateway.sh"
echo "4. Complete setup on gateway instance"
