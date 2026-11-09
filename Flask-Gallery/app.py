import os
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'kunci-rahasia-galeri-123'

# Konfigurasi Database SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///galeri.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Konfigurasi Folder Penyimpanan (Drive / Folder Lokal)
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp', 'mp4', 'webm', 'mov'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # Maksimal 50MB per file

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db = SQLAlchemy(app)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), unique=True, nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def sync_folder_to_db():
    """
    ALGORITMA SINKRONISASI:
    Mencocokkan file fisik di dalam folder uploads dengan database SQLite secara otomatis.
    """
    if not os.path.exists(UPLOAD_FOLDER):
        return

    # 1. Ambil semua nama file fisik di folder
    files_in_folder = set(f for f in os.listdir(UPLOAD_FOLDER) if allowed_file(f))

    # 2. Ambil semua nama file di database
    photos_in_db = Photo.query.all()
    files_in_db = set(p.filename for p in photos_in_db)

    # 3. Jika ada file baru ditambahkan langsung ke folder
    new_files = files_in_folder - files_in_db
    for filename in new_files:
        title_auto = os.path.splitext(filename)[0].replace('_', ' ').title()
        new_media = Photo(
            filename=filename,
            title=title_auto,
            description="Ditambahkan melalui sinkronisasi folder lokal."
        )
        db.session.add(new_media)

    # 4. Jika file dihapus langsung dari folder
    deleted_files = files_in_db - files_in_folder
    if deleted_files:
        Photo.query.filter(Photo.filename.in_(deleted_files)).delete(synchronize_session=False)

    db.session.commit()

@app.route('/')
def index():
    # Jalankan sinkronisasi otomatis setiap kali halaman dibuka / direfresh
    sync_folder_to_db()
    
    photos = Photo.query.order_by(Photo.upload_date.desc()).all()
    return render_template('index.html', photos=photos)

@app.route('/upload', methods=['POST'])
def upload_photo():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    
    if 'file' not in request.files:
        flash('Tidak ada file yang dipilih!', 'danger')
        return redirect(url_for('index'))
        
    file = request.files['file']

    if file.filename == '':
        flash('Pilih berkas media terlebih dahulu!', 'warning')
        return redirect(url_for('index'))

    if not title:
        flash('Judul media tidak boleh kosong!', 'warning')
        return redirect(url_for('index'))

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)

        existing_photo = Photo.query.filter_by(filename=filename).first()
        if not existing_photo:
            new_media = Photo(filename=filename, title=title, description=description)
            db.session.add(new_media)
            db.session.commit()

        flash('Media berhasil diunggah dan disinkronkan!', 'success')
        return redirect(url_for('index'))
    else:
        flash('Format file tidak didukung!', 'danger')
        return redirect(url_for('index'))

@app.route('/edit/<int:photo_id>', methods=['POST'])
def edit_media(photo_id):
    media = Photo.query.get_or_404(photo_id)
    
    new_title = request.form.get('title', '').strip()
    new_description = request.form.get('description', '').strip()
    
    if new_title:
        media.title = new_title
    media.description = new_description
    
    db.session.commit()
    flash('Media berhasil diperbarui!', 'success')
    return redirect(url_for('index'))

@app.route('/delete/<int:photo_id>', methods=['POST'])
def delete_photo(photo_id):
    media = Photo.query.get_or_404(photo_id)
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], media.filename)
    
    if os.path.exists(filepath):
        os.remove(filepath)

    db.session.delete(media)
    db.session.commit()

    flash('Media berhasil dihapus.', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)