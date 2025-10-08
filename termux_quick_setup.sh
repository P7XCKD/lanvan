#!/bin/bash
# 🚀 LANVAN Termux One-Command Setup
# Copy and paste this ENTIRE block into Termux (all lines at once)

echo "🚀 LANVAN Final Setup Starting..."

# Update and install packages
pkg update && pkg upgrade -y
pkg install -y python python-pip git clang make cmake libjpeg-turbo-dev zlib-dev libffi-dev

# Setup storage
termux-setup-storage

# Create project directory
cd $HOME && mkdir -p lanvan && cd lanvan

# Create Android requirements
cat > requirements-android.txt << 'EOF'
fastapi>=0.104.1
uvicorn[standard]>=0.24.0
jinja2>=3.1.2
python-multipart>=0.0.6
qrcode[pil]>=7.4.2
pillow>=10.0.0
aiofiles>=23.2.0
zeroconf>=0.132.2
psutil>=5.9.6
cryptography>=41.0.7
websockets>=11.0.2
wsproto>=1.2.0
EOF

# Install Python packages
pip install --upgrade pip
pip install -r requirements-android.txt

# Create directories
mkdir -p app uploads temp_chunks certs
mkdir -p app/static app/templates

echo "✅ Base setup complete!"

# Copy your project files here or use git clone
echo "📁 Now copy your LANVAN project files to: $HOME/lanvan/"
echo "   Or use: git clone [your-repo-url] ."
echo ""
echo "🚀 Once files are copied, start with:"
echo "   python run_termux.py"
echo ""
echo "🎯 This setup includes:"
echo "   ✅ All dependencies for Termux"
echo "   ✅ Proper directory structure" 
echo "   ✅ Android-optimized requirements"
echo "   ✅ Storage permissions"
echo ""
echo "💡 Remember to configure Android settings:"
echo "   Settings → Apps → Termux → Battery → Don't optimize"