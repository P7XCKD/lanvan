from app import app
from flask import render_template

@app.route('/')
def home():
    return render_template("index.html", msg="🚀 Secure LAN server is running!")
