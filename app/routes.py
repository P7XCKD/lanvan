import os
from flask import Blueprint, render_template, request, redirect, url_for, send_from_directory, current_app

main = Blueprint('main', __name__)

@main.route('/')
def home():
    files = os.listdir(current_app.config['UPLOAD_FOLDER'])
    return render_template("index.html", msg="🚀 Secure LAN server is running!", files=files)

@main.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part"
    file = request.files['file']
    if file.filename == '':
        return "No selected file"
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)
    return redirect(url_for('main.home'))

@main.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename, as_attachment=True)
@main.route('/clear', methods=['POST'])
def clear_files():
    folder = current_app.config['UPLOAD_FOLDER']
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
    return redirect(url_for('main.home'))
