from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
import sqlite3, bcrypt
import json, os
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from itsdangerous import URLSafeTimedSerializer

# ===== 1️⃣ Create Flask app =====
app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with a strong random value

# ===== 2️⃣ Database paths =====
DATABASE_PATH = os.path.join(app.root_path, "database.db")
ORDERS_FILE = os.path.join(app.root_path, "orders.json")

# ===== 3️⃣ Token serializer =====
s = URLSafeTimedSerializer(app.secret_key)

# ===== 4️⃣ Email helper =====
def send_reset_email(to_email, reset_link, user_name):
    sender_email = "your_email@gmail.com"
    sender_password = "your_app_password"

    message = MIMEMultipart()
    message["From"] = sender_email
    message["To"] = to_email
    message["Subject"] = "Password Reset Request"

    body = f"""Hello {user_name},

Click the link below to reset your password:

{reset_link}

This link will expire in 30 minutes.
"""
    message.attach(MIMEText(body, "plain"))

    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender_email, sender_password)
        server.send_message(message)
        server.quit()
    except Exception as e:
        print("Email sending error:", e)  # Prevent crash

# ===== 5️⃣ Database helpers =====
def get_db():
    con = sqlite3.connect(DATABASE_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con

def init_db():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                password BLOB NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS login_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_name TEXT,
                email TEXT,
                login_time TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        con.commit()

# Initialize DB
init_db()

# ===== Decorators =====
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

# ===== Routes =====
@app.route("/")
def index():
    return redirect(url_for("login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")

        if not name or not email or not password:
            flash("Please fill all required fields.", "danger")
            return redirect(url_for("register"))

        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        try:
            with get_db() as con:
                cur = con.cursor()
                cur.execute(
                    "INSERT INTO users (name, email, phone, password) VALUES (?, ?, ?, ?)",
                    (name, email, phone, hashed_pw),
                )
                con.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already exists. Try logging in.", "danger")
            return redirect(url_for("register"))
        except Exception as e:
            flash("Error during registration.", "danger")
            print("DB Error:", e)
            return redirect(url_for("register"))

    return render_template("register.html")

@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as con:
            cur = con.cursor()
            cur.execute("SELECT id, name, password FROM users WHERE email=?", (email,))
            user = cur.fetchone()

        if user:
            try:
                if bcrypt.checkpw(password.encode("utf-8"), user["password"]):
                    session["user_id"] = user["id"]
                    session["user_name"] = user["name"]

                    # Log login
                    try:
                        with get_db() as con:
                            cur = con.cursor()
                            cur.execute("""
                                INSERT INTO login_log (user_id, user_name, email, login_time)
                                VALUES (?, ?, ?, ?)
                            """, (user["id"], user["name"], email, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
                            con.commit()
                    except Exception as e:
                        print("Login log error:", e)

                    flash("Login successful!", "success")
                    return redirect(url_for("home"))
            except Exception:
                flash("Authentication error. Try again.", "danger")
                return redirect(url_for("login"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for("login"))

# ===== Password reset =====
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        try:
            with get_db() as con:
                cur = con.cursor()
                cur.execute("SELECT id, name FROM users WHERE email=?", (email,))
                user = cur.fetchone()

            if user:
                token = s.dumps(email, salt='password-reset-salt')
                reset_link = url_for('reset_password', token=token, _external=True)
                try:
                    send_reset_email(email, reset_link, user["name"])
                except Exception as e:
                    print("Email send failed:", e)

            flash('If your email exists, a password reset link has been sent.', 'info')
            return redirect(url_for('login'))
        except Exception as e:
            flash("Error processing password reset.", "danger")
            print("Password reset error:", e)
            return redirect(url_for('forgot_password'))

    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=1800)
    except Exception:
        flash('The password reset link is invalid or expired.', 'danger')
        return redirect(url_for('login'))  # ✅ Go to login page

    if request.method == 'POST':
        password = request.form['password']
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        try:
            with get_db() as con:
                cur = con.cursor()
                cur.execute("UPDATE users SET password=? WHERE email=?", (hashed_pw, email))
                con.commit()
            flash('Your password has been reset successfully!', 'success')
            return redirect(url_for('login'))
        except Exception as e:
            flash('Error resetting password.', 'danger')
            print("Reset DB error:", e)
            return redirect(url_for('login'))

    return render_template('reset_password.html')

# ===== Run app =====
if __name__ == "__main__":
    app.run(debug=True, port=5001)



