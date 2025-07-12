from flask import Flask

# Explicitly tell Flask that templates are outside the app/ folder
app = Flask(__name__, template_folder="../templates")

from app import routes
