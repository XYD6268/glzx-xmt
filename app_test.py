from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
from PIL import Image
import os

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///photos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['THUMB_FOLDER'] = 'static/thumbs'
db = SQLAlchemy(app)

class Photo(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(128))
    thumb_url = db.Column(db.String(128))
    class_name = db.Column(db.String(32))
    student_name = db.Column(db.String(32))
    vote_count = db.Column(db.Integer, default=0)

@app.route('/')
def index():
    photos = Photo.query.all()
    contest_title = "2025年摄影比赛"
    return render_template('index.html', contest_title=contest_title, photos=photos)

@app.route('/vote', methods=['POST'])
def vote():
    data = request.get_json()
    photo_id = data.get('photo_id')
    photo = Photo.query.get(photo_id)
    if photo:
        photo.vote_count += 1
        db.session.commit()
        return jsonify({'vote_count': photo.vote_count})
    return jsonify({'error': 'not found'}), 404

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        file = request.files['photo']
        class_name = request.form['class_name']
        student_name = request.form['student_name']
        filename = secure_filename(file.filename)
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(save_path)
        # 生成缩略图
        thumb_path = os.path.join(app.config['THUMB_FOLDER'], filename)
        img = Image.open(save_path)
        img.thumbnail((180, 120))
        img.save(thumb_path)
        # 写入数据库
        photo = Photo(url='/' + save_path.replace('\\', '/'), thumb_url='/' + thumb_path.replace('\\', '/'), class_name=class_name, student_name=student_name)
        db.session.add(photo)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('upload.html')

if __name__ == '__main__':
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(app.config['THUMB_FOLDER'], exist_ok=True)
    with app.app_context():
        db.create_all()
    app.run(debug=True)
