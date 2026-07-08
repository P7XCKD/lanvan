#!/data/data/com.termux/files/usr/bin/bash
# Run this script in Termux to set up all dependencies

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

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

# Configure Android API level environment variables for Rust/maturin builds
echo "⚙️ Configuring Android API environment variables..."
if ! grep -q "ANDROID_API_LEVEL" ~/.bashrc 2>/dev/null; then
    echo 'export ANDROID_API_LEVEL=24' >> ~/.bashrc
fi
export ANDROID_API_LEVEL=24

if ! grep -q "ANDROID_API=24" ~/.bashrc 2>/dev/null; then
    echo 'export ANDROID_API=24' >> ~/.bashrc
fi
export ANDROID_API=24

# Update package list and full upgrade to keep system libraries in sync (fixes curl/openssl mismatches)
echo "📦 Updating and upgrading Termux packages..."
pkg update -y && pkg upgrade -y

# Install essential system packages, build tools, and precompiled Python packages
echo "🔧 Installing system dependencies and precompiled Python packages..."
pkg install -y python python-pip git curl wget clang make cmake rust \
            python-cryptography python-psutil

# Install remaining lightweight and pure-Python packages via pip
echo "🐍 Installing remaining Python packages via pip..."
python -m pip install --upgrade pip setuptools wheel
python -m pip install fastapi uvicorn jinja2 python-multipart aiofiles qrcode zeroconf websockets wsproto brotli pyperclip uvloop || echo "⚠️ Some pip packages failed to install, proceeding..."

# Verify python imports
echo "🔍 Verifying dependency imports..."
python -c "
libs = ['fastapi', 'uvicorn', 'jinja2', 'multipart', 'cryptography', 'psutil', 'qrcode', 'zeroconf', 'aiofiles', 'websockets', 'wsproto', 'brotli', 'uvloop']
missing = []
for lib in libs:
    try:
        __import__(lib)
    except ImportError:
        missing.append(lib)
if missing:
    print('❌ Failed to import some libraries:', missing)
    exit(1)
else:
    print('✅ All imports verified successfully!')
" || { echo "❌ Dependency verification failed. Please check the logs above."; exit 1; }

# Set up storage permissions
echo "📁 Setting up storage permissions..."
termux-setup-storage

# Create lanvan directory in home
echo "📂 Setting up lanvan directory..."
cd $HOME
if [ ! -d "lanvan" ]; then
    mkdir -p lanvan
fi

# Copy preconfigured launch scripts to home directory
echo "🚀 Copying startup scripts to home directory..."
if [ -f "$SCRIPT_DIR/start-server.sh" ]; then
    cp "$SCRIPT_DIR/start-server.sh" "$HOME/start_server.sh"
    chmod +x "$HOME/start_server.sh"
    echo "   [OK] Copied start_server.sh to ~/"
fi
if [ -f "$SCRIPT_DIR/start-server-https.sh" ]; then
    cp "$SCRIPT_DIR/start-server-https.sh" "$HOME/start_server1.sh"
    chmod +x "$HOME/start_server1.sh"
    echo "   [OK] Copied start_server1.sh to ~/"
fi

echo ""
echo "✅ Lanvan Android/Termux setup completed!"
echo ""
echo "📋 Next steps:"
echo "1. Run the server using: ~/start_server.sh"
echo "   (or run ~/start_server1.sh for HTTPS mode)"
echo ""
echo "💡 Tips for Android/Termux:"
echo "• Use direct IP access instead of .local domains"
echo "• QR codes will be generated for easy mobile access"
echo "• Keep Termux app active to prevent server shutdown"
echo "• Use 'termux-wake-lock' to prevent device sleep"
echo ""
echo "🚨 Known limitations:"
echo "• .local mDNS domains often don't work on Android"
echo "• Clipboard sync may be limited by Android permissions"
echo ""