from flask import Flask, request, jsonify, render_template, redirect, session
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import sqlite3
import requests

app = Flask(__name__)
app.secret_key = 'secret123'
CORS(app)

socketio = SocketIO(app, cors_allowed_origins="*")

online_users = {}

# ---------- DATABASE ----------
def init_db():
    conn = sqlite3.connect('startly.db')
    c = conn.cursor()

    # USERS
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        email TEXT,
        password TEXT,
        skills TEXT,
        goals TEXT
    )''')

    # MESSAGES
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sender_id INTEGER,
        receiver_id INTEGER,
        message TEXT
    )''')

    # IDEAS
    c.execute('''CREATE TABLE IF NOT EXISTS ideas (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        content TEXT
    )''')

    # LIKES
    c.execute('''CREATE TABLE IF NOT EXISTS likes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        idea_id INTEGER
    )''')

    # COMMENTS
    c.execute('''CREATE TABLE IF NOT EXISTS comments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        idea_id INTEGER,
        comment TEXT
    )''')

    conn.commit()
    conn.close()

init_db()

# ---------- ROUTES ----------
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.form

    conn = sqlite3.connect('startly.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users WHERE email=? AND password=?",
              (data['email'], data['password']))
    user = c.fetchone()
    conn.close()

    if user:
        session['user_id'] = user[0]
        return redirect('/feed')
    return "Invalid login"

@app.route('/feed')
def feed():
    if 'user_id' not in session:
        return redirect('/')
    return render_template('feed.html')

# USERS
@app.route('/matches')
def matches():
    conn = sqlite3.connect('startly.db')
    c = conn.cursor()
    c.execute("SELECT * FROM users")
    data = c.fetchall()
    conn.close()
    return jsonify(data)

# IDEAS
@app.route('/add_idea', methods=['POST'])
def add_idea():
    user = session['user_id']
    content = request.json['content']

    conn = sqlite3.connect('startly.db')
    c = conn.cursor()
    c.execute("INSERT INTO ideas (user_id, content) VALUES (?,?)",
              (user, content))
    conn.commit()
    conn.close()

    return jsonify({"message": "Idea posted"})

@app.route('/ideas')
def ideas():
    conn = sqlite3.connect('startly.db')
    c = conn.cursor()

    c.execute("""
        SELECT ideas.id, users.name, ideas.content
        FROM ideas
        JOIN users ON ideas.user_id = users.id
        ORDER BY ideas.id DESC
    """)

    data = c.fetchall()
    conn.close()
    return jsonify(data)

# LIKE
@app.route('/like', methods=['POST'])
def like():
    user = session['user_id']
    idea_id = request.json['idea_id']

    conn = sqlite3.connect('startly.db')
    c = conn.cursor()
    c.execute("INSERT INTO likes (user_id, idea_id) VALUES (?,?)",
              (user, idea_id))
    conn.commit()
    conn.close()

    return jsonify({"message": "Liked"})

# COMMENT
@app.route('/comment', methods=['POST'])
def comment():
    user = session['user_id']
    idea_id = request.json['idea_id']
    text = request.json['comment']

    conn = sqlite3.connect('startly.db')
    c = conn.cursor()
    c.execute("INSERT INTO comments (user_id, idea_id, comment) VALUES (?,?,?)",
              (user, idea_id, text))
    conn.commit()
    conn.close()

    return jsonify({"message": "Comment added"})

@app.route('/comments/<int:idea_id>')
def get_comments(idea_id):
    conn = sqlite3.connect('startly.db')
    c = conn.cursor()

    c.execute("""
        SELECT users.name, comments.comment
        FROM comments
        JOIN users ON comments.user_id = users.id
        WHERE idea_id=?
    """, (idea_id,))

    data = c.fetchall()
    conn.close()

    return jsonify(data)

# 🤖 KURAMA AI
@app.route('/kurama', methods=['POST'])
def kurama():
    msg = request.json['message']

    API_URL = "https://api-inference.huggingface.co/models/google/flan-t5-large"
    headers = {"Authorization": "Bearer YOUR_HUGGINGFACE_API_KEY"}

    try:
        res = requests.post(API_URL, headers=headers,
                            json={"inputs": msg})
        reply = res.json()[0]['generated_text']
    except:
        reply = "Kurama is thinking..."

    return jsonify({"reply": reply})

# ---------- SOCKET.IO ----------
@socketio.on('connect')
def connect():
    user_id = session.get('user_id')
    if user_id:
        online_users[user_id] = request.sid
        emit('online_users', list(online_users.keys()), broadcast=True)

@socketio.on('disconnect')
def disconnect():
    for uid, sid in list(online_users.items()):
        if sid == request.sid:
            del online_users[uid]
    emit('online_users', list(online_users.keys()), broadcast=True)

@socketio.on('send_message')
def handle_msg(data):
    sender = session.get('user_id')
    receiver = data['receiver_id']
    msg = data['message']

    conn = sqlite3.connect('startly.db')
    c = conn.cursor()
    c.execute("INSERT INTO messages (sender_id, receiver_id, message) VALUES (?,?,?)",
              (sender, receiver, msg))
    conn.commit()
    conn.close()

    if receiver in online_users:
        emit('receive_message', {"message": msg}, room=online_users[receiver])

    emit('receive_message', {"message": msg})

if __name__ == '__main__':
    socketio.run(app, debug=True)