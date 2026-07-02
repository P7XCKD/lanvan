#!/data/data/com.termux/files/usr/bin/bash
# Android/Termux Setup Script for Lanvan File Server
# Run this script in Termux to set up all dependencies
# DO NOTE THAT THIS SCRIPT HASNT BEEN TESTED YET


echo "🤖 Lanvan Android/Termux Setup Script"
echo "======================================"
echo ""

# Check if we're actually running in Termux
if [ ! -d "/data/data/com.termux" ]; then
    echo "❌ This script is designed for Android Termux environment"
    echo "   Please run this in Termux app"
    exit 1
fi

echo "✅ Termux environment detected"
echo ""

# Update package list
echo "📦 Updating Termux packages..."
pkg update -y

# Install essential system packages
echo "🔧 Installing system dependencies..."
pkg install -y python python-pip git curl wget

# Install build dependencies for Python packages
echo "🛠️ Installing build dependencies..."
pkg install -y clang make cmake libjpeg-turbo-dev zlib-dev

# Upgrade pip
echo "⬆️ Upgrading pip..."
python -m pip install --upgrade pip

# Install Python dependencies with Android optimizations
echo "🐍 Installing Python dependencies..."

# Install core packages first
python -m pip install --upgrade fastapi uvicorn[standard] jinja2 python-multipart

# Install QR code support with pillow
echo "📱 Installing QR code support..."
python -m pip install --upgrade pillow qrcode[pil]

# Install networking packages
echo "🌐 Installing network packages..."
python -m pip install --upgrade zeroconf aiofiles psutil

# Install security packages
echo "🔐 Installing security packages..."
python -m pip install --upgrade cryptography

# Install WebSocket support
echo "🔌 Installing WebSocket support..."
python -m pip install --upgrade websockets wsproto

# Optional: Install clipboard support (might not work on all Android versions)
echo "📋 Attempting to install clipboard support..."
python -m pip install --upgrade pyperclip || echo "⚠️ Clipboard support failed (this is normal on Android)"

# Set up storage permissions
echo "📁 Setting up storage permissions..."
termux-setup-storage

# Create Lanvan directory in home
echo "📂 Setting up Lanvan directory..."
cd $HOME
if [ ! -d "Lanvan" ]; then
    mkdir -p lanvan
fi

echo ""
echo "✅ Lanvan Android/Termux setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Copy your Lanvan project files to ~/lanvan/"
echo "2. cd ~/lanvan"
echo "3. python run.py"
echo ""
echo "💡 Tips for Android/Termux:"
echo "• Use direct IP access instead of .local domains"
echo "• QR codes will be generated for easy mobile access"
echo "• Keep Termux app active to prevent server shutdown"
echo "• Use 'termux-wake-lock' to prevent device sleep"
echo ""
echo "🚨 Known limitations:"
echo "• Some WebRTC features may not work on mobile"
echo "• .local mDNS domains often don't work on Android"
echo "• Clipboard sync may be limited by Android permissions"
echo ""