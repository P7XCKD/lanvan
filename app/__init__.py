from flask import Flask
import os
from flask_compress import Compress

# Initialize Flask app
app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Configure uploads path
app.config['UPLOAD_FOLDER'] = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads'))
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

app.config['MAX_CONTENT_LENGTH'] = 15 * 1024 * 1024 * 1024  # 15 GB

# Register blueprint
from app.routes import main
app.register_blueprint(main)

# Initialize compression
compress = Compress()
compress.init_app(app)

# ✅ Expose app so that "from app import app" works
__all__ = ['app']
