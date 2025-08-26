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
        print("Error sending email:", e)

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
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                user_name TEXT,
                customer_name TEXT,
                email TEXT,
                phone TEXT,
                address TEXT,
                payment_method TEXT,
                items TEXT,
                total REAL,
                date TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
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

# ===== Sample products =====
products = [
    {"name": "Herbal Face Cream", "description": "Natural ingredients for glowing skin", "price": 250, "image": "images/herbalfacecream.jpg"},
    {"name": "Aloe Vera Gel", "description": "Soothes and hydrates the skin", "price": 180, "image": "images/aleovera.jpg"},
    {"name": "Ghar Soap", "description": "Pure herbal bathing soap", "price": 70,  "image": "images/gharsoap.jpg"},
    {"name": "Lotus Powder", "description": "Skin brightening herbal powder", "price": 120, "image": "images/lotus.jpg"},
    {"name": "Ayur Herbal Shampoo", "description": "Gentle cleansing for hair", "price": 300, "image": "images/ayurherbal.jpg"},
    {"name": "Aloe Allen Juice", "description": "Detoxifying aloe vera juice", "price": 200, "image": "images/aloeallen.jpg"},
    {"name": "Eladi Oil", "description": "Traditional ayurvedic oil for skin", "price": 400, "image": "images/eladi.jpg"},
]

# ===== Decorators =====
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("user_id"):
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if session.get("user_name") != "Admin":
            flash("Access denied!", "danger")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated

# ===== 6️⃣ Routes =====

# Default route → Login page
@app.route("/")
def home():
    return redirect(url_for("login"))

# ✅ Register Page
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        phone = request.form["phone"].strip()
        password = request.form["password"]

        hashed_pw = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())

        try:
            with get_db() as con:
                cur = con.cursor()
                cur.execute("""
                    INSERT INTO users (name, email, phone, password)
                    VALUES (?, ?, ?, ?)
                """, (name, email, phone, hashed_pw))
                con.commit()
            flash("Registration successful! Please log in.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already exists!", "danger")
    return render_template("register.html")

# ✅ Login Page
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as con:
            cur = con.cursor()
            cur.execute("SELECT id, name, email, phone, password FROM users WHERE email=?", (email,))
            user = cur.fetchone()

        if user:
            stored_pw = user["password"]
            if bcrypt.checkpw(password.encode("utf-8"), stored_pw):
                session["user_id"] = user["id"]
                session["user_name"] = user["name"]

                with get_db() as con:
                    cur = con.cursor()
                    cur.execute("""
                        INSERT INTO login_log (user_id, user_name, email, login_time)
                        VALUES (?, ?, ?, ?)
                    """, (
                        user["id"],
                        user["name"],
                        user["email"],
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ))
                    con.commit()

                flash("Login successful!", "success")
                return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "danger")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for("login"))

# ✅ Dashboard
@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")

# ✅ Products Page
@app.route("/products")
@login_required
def products_page():
    return render_template("products.html")

# ✅ Place Order
@app.route("/place-order", methods=["POST"])
@login_required
def place_order():
    data = request.form
    order = {
        "user_id": session["user_id"],
        "user_name": session["user_name"],
        "customer_name": data.get("customer_name"),
        "email": data.get("email"),
        "phone": data.get("phone"),
        "address": data.get("address"),
        "payment_method": data.get("payment_method"),
        "items": data.get("items"),
        "total": data.get("total"),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    with get_db() as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO orders (user_id, user_name, customer_name, email, phone, address, payment_method, items, total, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            order["user_id"], order["user_name"], order["customer_name"], order["email"], order["phone"],
            order["address"], order["payment_method"], order["items"], order["total"], order["date"]
        ))
        con.commit()

    flash("Order placed successfully!", "success")
    return redirect(url_for("order_history"))

# ✅ Order History
@app.route("/order-history")
@login_required
def order_history():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM orders WHERE user_id=?", (session["user_id"],))
        orders = cur.fetchall()
    return render_template("order_history.html", orders=orders)

# ✅ Forgot Password
@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        with get_db() as con:
            cur = con.cursor()
            cur.execute("SELECT id, name FROM users WHERE email=?", (email,))
            user = cur.fetchone()

        if user:
            token = s.dumps(email, salt='password-reset-salt')
            reset_link = url_for('reset_password', token=token, _external=True)
            send_reset_email(email, reset_link, user["name"])

        flash('If your email exists in our system, a password reset link has been sent.', 'info')
        return redirect(url_for('login'))
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        email = s.loads(token, salt='password-reset-salt', max_age=1800)
    except Exception:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form['password']
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        with get_db() as con:
            cur = con.cursor()
            cur.execute("UPDATE users SET password=? WHERE email=?", (hashed_pw, email))
            con.commit()
        flash('Your password has been reset successfully!', 'success')
        return redirect(url_for('login'))
    return render_template('reset_password.html')

# ✅ Admin Dashboard (optional)
@app.route("/admin")
@admin_required
def admin_dashboard():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM orders")
        orders = cur.fetchall()
    return render_template("admin_dashboard.html", orders=orders)

# ✅ Route to display Contact Page
@app.route("/contact")
def contact():
    return render_template("contact.html")

# ✅ Route to handle form submission
@app.route("/send_message", methods=["POST"])
def send_message():
    if request.method == "POST":
        name = request.form.get("name")
        email = request.form.get("email")
        message = request.form.get("message")

        # ✅ Here you can process the data (save to DB or send email)
        print(f"Name: {name}, Email: {email}, Message: {message}")

        flash("Your message has been sent successfully!", "success")
        return redirect(url_for("contact"))


# ✅ Cart Route
@app.route("/cart")
def cart():
    cart_items = session.get("cart", [])
    total = sum(item["price"] for item in cart_items)
    return render_template("cart.html", cart_items=cart_items, total=total)

# ✅ Add item to cart
@app.route("/add_to_cart", methods=["POST"])
def add_to_cart():
    product_name = request.form.get("name")
    price = float(request.form.get("price"))
    image = request.form.get("image")

    # Initialize cart if empty
    if "cart" not in session:
        session["cart"] = []

    session["cart"].append({"name": product_name, "price": price, "image": image})
    session.modified = True

    flash(f"{product_name} added to cart!", "success")
    return redirect(url_for("products_page"))

# ✅ Remove single item from cart
@app.route("/remove_from_cart/<product_name>")
def remove_from_cart(product_name):
    cart = session.get("cart", [])
    session["cart"] = [item for item in cart if item["name"] != product_name]
    session.modified = True
    flash(f"{product_name} removed from cart.", "info")
    return redirect(url_for("cart"))

# ✅ Clear all items
@app.route("/clear_cart")
def clear_cart():
    session.pop("cart", None)
    flash("All items removed from your cart.", "warning")
    return redirect(url_for("cart"))

# ✅ Checkout
@app.route("/checkout")
def checkout():
    if not session.get("cart"):
        flash("Your cart is empty!", "error")
        return redirect(url_for("cart"))
    
    # For now, just clear the cart after checkout
    session.pop("cart", None)
    return "<h2>Thank you for your order!</h2>"

# ===== Run app =====
if __name__ == "__main__":
    app.run(debug=True, port=5001)


