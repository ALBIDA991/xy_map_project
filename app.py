from flask import Flask, request, session, redirect, render_template, jsonify
import sqlite3
from functools import wraps
from werkzeug.utils import secure_filename
import csv
import io
import os

# DBはRenderの書き込み可能な一時領域 /tmp に置く
DB_PATH = "/tmp/coords.db"

app = Flask(__name__, template_folder="templates")
app.secret_key = 'your_secret_key'

def get_db_connection():
    return sqlite3.connect(DB_PATH)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect('/login')
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pwd = request.form['password']
        if pwd == 'uajt991':
            session['username'] = user
            return redirect('/')
        return "ログイン失敗"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

@app.route('/')
@login_required
def home():
    return render_template('map.html')

@app.route('/admin')
@login_required
def admin_page():
    if session.get('username') != 'admin':
        return "許可されていません", 403
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT x, y, username FROM user_coords ORDER BY username ASC, x ASC, y ASC")
    user_coords = c.fetchall()
    c.execute("SELECT x, y, level FROM allowed_coords ORDER BY x ASC, y ASC")
    allowed_coords = c.fetchall()
    conn.close()
    return render_template('admin.html', user_coords=user_coords, allowed_coords=allowed_coords)

@app.route('/add_coord', methods=['POST'])
@login_required
def add_coord():
    data = request.json
    x, y = data.get('x'), data.get('y')
    user = session['username']
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT 1 FROM allowed_coords WHERE x=? AND y=?", (x, y))
    if not c.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "この座標は登録できません。"})
    c.execute("SELECT 1 FROM user_coords WHERE x=? AND y=?", (x, y))
    if c.fetchone():
        conn.close()
        return jsonify({"status": "error", "message": "この座標はすでに登録されています。"})
    c.execute("INSERT INTO user_coords (x, y, username) VALUES (?, ?, ?)", (x, y, user))
    conn.commit()
    conn.close()
    return jsonify({"status": "success", "message": "座標を登録しました。"})

@app.route('/get_coords')
@login_required
def get_coords():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT x, y FROM user_coords")
    data = c.fetchall()
    conn.close()
    return jsonify(data)

@app.route('/get_allowed_coords')
@login_required
def get_allowed_coords():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("SELECT x, y, level FROM allowed_coords")
    data = c.fetchall()
    conn.close()
    return jsonify(data)

@app.route('/upload_csv', methods=['GET', 'POST'])
@login_required
def upload_csv():
    if session.get('username') != 'admin':
        return "許可されていません", 403
    if request.method == 'POST':
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            return "CSVファイルのみ対応しています"
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)
        conn = get_db_connection()
        c = conn.cursor()
        inserted = 0
        skipped = 0
        for row in reader:
            try:
                x, y = int(row['x']), int(row['y'])
                level = int(row['level'])
                if 1 <= level <= 7:
                    c.execute("INSERT OR REPLACE INTO allowed_coords (x, y, level) VALUES (?, ?, ?)", (x, y, level))
                    inserted += 1
                else:
                    skipped += 1
            except:
                skipped += 1
        conn.commit()
        conn.close()
        return f"{inserted}件の座標を登録しました（{skipped}件スキップ）"
    return render_template('upload.html')

@app.route('/upload_user_csv', methods=['GET', 'POST'])
@login_required
def upload_user_csv():
    if session.get('username') != 'admin':
        return "許可されていません", 403

    if request.method == 'POST':
        file = request.files['file']
        if not file or not file.filename.endswith('.csv'):
            return "CSVファイルのみ対応しています"

        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        reader = csv.DictReader(stream)

        conn = get_db_connection()
        c = conn.cursor()

        inserted = 0
        skipped = 0
        for row in reader:
            try:
                x = int(row['x'])
                y = int(row['y'])
                username = row.get('username', 'unknown')
                c.execute("INSERT OR IGNORE INTO user_coords (x, y, username) VALUES (?, ?, ?)", (x, y, username))
                inserted += 1
            except Exception:
                skipped += 1
        conn.commit()
        conn.close()
        return f"{inserted}件登録、{skipped}件スキップしました"
    
    return render_template('upload_user.html')

@app.route('/init_db')
def init_db():
    seed_allowed_coords()
    return "DB initialized"

def seed_allowed_coords():
    conn = get_db_connection()
    c = conn.cursor()
    c.execute("CREATE TABLE IF NOT EXISTS allowed_coords (x INTEGER, y INTEGER, level INTEGER, PRIMARY KEY (x, y))")
    c.execute("CREATE TABLE IF NOT EXISTS user_coords (x INTEGER, y INTEGER, username TEXT, PRIMARY KEY (x, y))")
    conn.commit()
    conn.close()

if __name__ == '__main__':
    seed_allowed_coords()
    app.run(debug=True)