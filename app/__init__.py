import os
from flask import Flask

app = Flask(__name__, template_folder='../templates', static_folder='../static')

# Absolute path to uploads folder
app.config['UPLOAD_FOLDER'] = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'uploads'))
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Register Blueprint
from app.routes import main
app.register_blueprint(main)
