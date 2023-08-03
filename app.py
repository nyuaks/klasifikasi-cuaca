from flask import Flask, render_template, Response, request, jsonify, redirect, url_for, session, flash
from flask_mysqldb import MySQL, MySQLdb
import bcrypt 
from werkzeug.utils import secure_filename
import cv2
from tensorflow.keras.models import load_model
import numpy as np
import os

app = Flask(__name__)
app.secret_key = "AnDhIBAGUSpratama612001"

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'flaskdb'
app.config['MYSQL_CURSORCLASS'] = 'DictCursor'
mysql = MySQL(app)
mydb = MySQLdb.connect(host = 'localhost',user = 'root',passwd = '',db = 'flaskdb')

model = load_model('model.h5')

frame_count = 0
current_label = None
video_upload_path = 'static\\uploads'

@app.route('/')
def home() :
    return render_template("home.html")

def classify_frame(frame):
    global frame_count, current_label

    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    frame = cv2.resize(frame, (224, 224))
    frame = np.expand_dims(frame, axis=0)
    frame = frame / 255.0

    if frame_count % 20 == 0:
        prediction = model.predict(frame)

        if prediction[0][0] > prediction[0][1]:
            current_label = 'CERAH ('+ str(prediction[0][0])+')'
        else:
            current_label = 'HUJAN ('+ str(prediction[0][1])+')'

    frame_count += 1
    return current_label

def generate_frames(video):
    video_path = 'uploads'
    video_file_path = os.path.join(video_path, video)
    cap = cv2.VideoCapture(video)

    while True:
        ret, frame = cap.read()

        if not ret:
            break

        label = classify_frame(frame)

        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1
        thickness = 2
        text_size, _ = cv2.getTextSize(label, font, scale, thickness)

        text_x = 50
        text_y = frame.shape[0] - 40
        cv2.putText(frame, label, (text_x, text_y), font, scale, (0, 255, 255), thickness, cv2.LINE_AA)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

    cap.release()
    
@app.route('/upload', methods=['POST'])
def upload():
    if 'video_file' not in request.files:
        flash('Tidak ada file yang diunggah!', 'error')
        return redirect(url_for('index'))

    video_file = request.files['video_file']
    if video_file.filename == '':
        flash('Tidak ada file yang dipilih!', 'error')
        return redirect(url_for('index'))

    if video_file and allowed_file(video_file.filename):
        video_filename = secure_filename(video_file.filename)  # Menggunakan secure_filename untuk mendapatkan nama file yang aman
        video_path = os.path.join(video_upload_path, video_filename)
        video_file.save(video_path)

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO video (nama,deskripsi,path) VALUES (%s,%s,%s)" ,(request.form['nama'],request.form['deskripsi'], video_path))
        mysql.connection.commit()
        cur.close()
        flash('Data berhasil diunggah!', 'success')
        return redirect(url_for('index'))
    else:
        flash('Format file tidak diizinkan!', 'error')
        return redirect(url_for('klasifikasi'))

def allowed_file(filename):
    # Tambahkan ekstensi file video yang diizinkan di sini
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in {'mp4'}

@app.route('/delete_video', methods=['POST'])
def delete_video():
    video_name = request.form.get('video_name')
    if video_name:
        uploads_dir = './uploads/'
        video_path = os.path.join(uploads_dir, video_name)
        if os.path.exists(video_path):
            os.remove(video_path)
            return jsonify({'status': 'success', 'message': 'Video berhasil dihapus.'})
        else:
            return jsonify({'status': 'error', 'message': 'Video tidak ditemukan.'})
    else:
        return jsonify({'status': 'error', 'message': 'Nama video tidak diberikan.'})

@app.route('/get_videos')
def get_videos():
    uploads_dir = './uploads/'
    video_files = [file for file in os.listdir(uploads_dir) if file.endswith('.mp4')]
    return {'videos': video_files}

@app.route('/video_feed')
def video_feed():
    video_name = request.args.get('video', '')
    return Response(generate_frames(video_name),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/login', methods=['GET', 'POST'])
def login(): 
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        curl = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        curl.execute("SELECT * FROM users WHERE email=%s",(email,))
        user = curl.fetchone()
        curl.close()

        if user is not None and len(user) > 0 :
            if bcrypt.hashpw(password, user['password'].encode('utf-8')) == user['password'].encode('utf-8'):
                session['name'] = user ['name']
                session['email'] = user['email']
                return redirect(url_for('index'))
            else :
                flash("Gagal, Email dan Password Tidak Cocok")
                return redirect(url_for('login'))
        else :
            flash("Gagal, User Tidak Ditemukan")
            return redirect(url_for('login'))
    else: 
        return render_template("login.html")

@app.route('/register', methods=['POST', 'GET'])
def register():
    if request.method=='GET':
        return render_template('register.html')
    else :
        name = request.form['name']
        email = request.form['email']
        password = request.form['password'].encode('utf-8')
        hash_password = bcrypt.hashpw(password, bcrypt.gensalt())

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (name,email,password) VALUES (%s,%s,%s)" ,(name, email, hash_password)) 
        mysql.connection.commit()
        session['name'] = request.form['name']
        session['email'] = request.form['email']
        return redirect(url_for('home'))
@app.route('/about')
def about():
    #if 'email' in session:
        return render_template("about.html")
    #else:
        #return redirect(url_for('home'))
@app.route('/klasifikasi')
def klasifikasi():
    #if 'email' in session:
    cur = None
    try:
        cur = mydb.cursor()
        cur.execute('SELECT * FROM video')
        results = cur.fetchall()
        return render_template("klasifikasi.html",results=results)
    except Exception as e:
        print(e)
    finally:
        cur.close()

    #else:
        #return redirect(url_for('home')) 
@app.route('/contact')
def contact():
    #if 'email' in session:

        return render_template("contact.html")
    #else:
        #return redirect(url_for('home')) 
@app.route('/index')
def index():
    if 'email' in session:
        cur = None
        try:
            cur = mydb.cursor()
            cur.execute('SELECT * FROM video')
            results = cur.fetchall()
            return render_template('admin/dashboard.html',results=results)
        except Exception as e:
            print(e)
        finally:
            cur.close()
    else:
        return redirect(url_for('home'))
@app.route('/formUploadVideo')
def formUploadVideo():
    return render_template('admin/upload.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/edit/<int:id>')
def edit_view(id):
    cursor = mydb.cursor()
    cursor.execute("SELECT * FROM video WHERE id=%s", (id,))
    row = cursor.fetchone()
    return render_template('admin/edit.html', row=row)

@app.route('/update', methods=['POST'])
def update_user():
    conn = None
    cursor = None
    try:
        _name = request.form['nama']
        _deskripsi = request.form['deskripsi']
        _id = request.form['id']
        # validate the received values
        if _name and _deskripsi and _id and request.method == 'POST':
            video_file = request.files['video_file']
            if video_file.filename == '':
                flash('Tidak ada file yang dipilih!', 'error')
                return redirect(url_for('index'))

            if video_file and allowed_file(video_file.filename):
                video_filename = secure_filename(video_file.filename)  # Menggunakan secure_filename untuk mendapatkan nama file yang aman
                video_path = os.path.join(video_upload_path, video_filename)
                video_file.save(video_path)
                sql = "UPDATE video SET nama=%s, deskripsi=%s, path=%s WHERE id=%s"
                data = (_name, _deskripsi, video_path, _id,)
                cursor = mydb.cursor()
                cursor.execute(sql, data)
                mydb.commit()
                flash('Data berhasil diubah!')
                return redirect('/index')
        else:
            return 'Error while updating user'
    except Exception as e:
        print(e)
    finally:
        cursor.close()

@app.route('/delete/<int:id>')
def delete_user(id):
    conn = None
    cursor = None
    try:
        cursor = mydb.cursor()
        cursor.execute("DELETE FROM video WHERE id=%s", (id,))
        mydb.commit()
        flash('Data berhasil dihapus!')
        return redirect('/index')
    except Exception as e:
        print(e)
    finally:
        cursor.close()

if __name__ == '__main__':
    app.run(debug=True)

    