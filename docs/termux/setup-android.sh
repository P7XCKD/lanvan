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

# Update package list and full upgrade to keep system libraries in sync (fixes curl/openssl mismatches)
echo "📦 Updating and upgrading Termux packages..."
pkg update -y && pkg upgrade -y

# Install essential system packages, build tools, and precompiled Python packages
echo "🔧 Installing system dependencies and precompiled Python packages..."
pkg install -y python python-pip git curl wget clang make cmake \
            python-cryptography python-psutil python-fastapi python-uvicorn \
            python-jinja python-websockets python-qrcode python-zeroconf

# Install remaining lightweight and pure-Python packages via pip
echo "🐍 Installing lightweight Python packages..."
python -m pip install python-multipart aiofiles wsproto brotli pyperclip || echo "⚠️ Some pip packages failed to install, proceeding..."

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