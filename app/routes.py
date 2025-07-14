import os
from flask import Blueprint, render_template, request, redirect, url_for, current_app, Response
from mimetypes import guess_type
from app.config import is_allowed_file

main = Blueprint('main', __name__)

@main.route('/')
def home():
    files = os.listdir(current_app.config['UPLOAD_FOLDER'])
    return render_template("index.html", msg="Lanvan", files=files)

@main.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return "No file part", 400

    file = request.files['file']
    if file.filename == '':
        return "No selected file", 400

    if not is_allowed_file(file.filename):
        return "File type not allowed", 400

    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], file.filename)
    file.save(filepath)
    return redirect(url_for('main.home'))

def generate_file_stream(file_path, chunk_size=65536):  # 64 KB
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


@main.route('/download/<filename>')
def download_file(filename):
    folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(folder, filename)

    if not os.path.isfile(file_path):
        return "File not found", 404

    mime_type, _ = guess_type(file_path)
    mime_type = mime_type or 'application/octet-stream'

    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"',
        'Content-Type': mime_type,
        'Content-Length': str(os.path.getsize(file_path)),
        'Cache-Control': 'public, max-age=86400'
    }

    return Response(generate_file_stream(file_path), headers=headers)

@main.route('/clear', methods=['POST'])
def clear_files():
    folder = current_app.config['UPLOAD_FOLDER']
    for filename in os.listdir(folder):
        file_path = os.path.join(folder, filename)
        if os.path.isfile(file_path):
            os.remove(file_path)
    return redirect(url_for('main.home'))

@main.route('/delete/<filename>', methods=['POST'])
def delete_file(filename):
    folder = current_app.config['UPLOAD_FOLDER']
    file_path = os.path.join(folder, filename)
    if os.path.isfile(file_path):
        os.remove(file_path)
    return redirect(url_for('main.home'))
