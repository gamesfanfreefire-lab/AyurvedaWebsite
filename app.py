from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
import sqlite3, bcrypt
import json, os, time, hashlib, secrets
from config import FLASK_SECRET, OTP_LENGTH, OTP_EXPIRY_SECONDS, OTP_RESEND_COOLDOWN, OTP_PEPPER
from mail_utils import send_email
from datetime import datetime
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature
import random
import smtplib
from flask import jsonify
from email.mime.text import MIMEText


app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with a strong random value

# ===== Email Config for Flask-Mail =====
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'krishnakudre.1205@gmail.com'  # Replace with your Gmail
app.config['MAIL_PASSWORD'] = 'ucrx pejy shxv pkmg'  # Gmail App Password
app.config['MAIL_DEFAULT_SENDER'] = 'krishnakudre.1205@gmail.com'

mail = Mail(app)

# Token Serializer
s = URLSafeTimedSerializer(app.secret_key)

# ===== SQLite: create users table if not exists =====
def _hash_otp(otp: str) -> str:
    return hashlib.sha256((otp + OTP_PEPPER).encode()).hexdigest()

def get_db():
    conn = sqlite3.connect("database.db")
    conn.row_factory = sqlite3.Row   # <-- return rows as dict-like objects
    return conn


def init_db():
    con = get_db()
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
            login_time TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS contact_messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL
        ) 
    """) 
# Products Table
    cur.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT,
            price REAL NOT NULL,
            image TEXT
        )
    """)
    cur.execute("DROP TABLE IF EXISTS orders")
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
        quantity INTEGER,
        total REAL,
        date TEXT
    )
""")


    # ✅ Insert sample products only if table is empty
    cur.execute("SELECT COUNT(*) FROM products")
    count = cur.fetchone()[0]

    if count == 0:  # Only insert if no products exist
        sample_products = [
            ("Herbal Face Cream", "Natural ingredients for glowing skin", 250, "images/herbalfacecream.jpg"),
            ("Aloe Vera Gel", "Soothes and hydrates the skin", 180, "images/aleovera.jpg"),
            ("Ghar Soap", "Pure herbal bathing soap", 70, "images/gharsoap.jpg"),
            ("Lotus Powder", "Skin brightening herbal powder", 120, "images/lotus.jpg"),
            ("Ayur Herbal Shampoo", "Gentle cleansing for hair", 300, "images/ayurherbal.jpg"),
            ("Aloe Allen Juice", "Detoxifying aloe vera juice", 200, "images/aloeallen.jpg"),
            ("Eladi Oil", "Traditional ayurvedic oil for skin", 400, "images/eladi.jpg")
        ]
        cur.executemany("INSERT INTO products (name, description, price, image) VALUES (?, ?, ?, ?)", sample_products)

                

    con.commit()
    con.close()

init_db()

# ===== File path for stored orders (JSON) =====
ORDERS_FILE = os.path.join(app.root_path, "orders.json")

def load_orders():
    if not os.path.exists(ORDERS_FILE):
        return []
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []

def save_orders(orders):
    os.makedirs(os.path.dirname(ORDERS_FILE), exist_ok=True)
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, ensure_ascii=False, indent=2)

# ===== Sample products =====
products = [
    {"id": 1, "name": "Herbal Face Cream", "description": "Natural ingredients for glowing skin", "price": 250, "image": "images/herbalfacecream.jpg"},
    {"id": 2, "name": "Aloe Vera Gel", "description": "Soothes and hydrates the skin", "price": 180, "image": "images/aleovera.jpg"},
    {"id": 3, "name": "Ghar Soap", "description": "Pure herbal bathing soap", "price": 70,  "image": "images/gharsoap.jpg"},
    {"id": 4, "name": "Lotus Powder", "description": "Skin brightening herbal powder", "price": 120, "image": "images/lotus.jpg"},
    {"id": 5, "name": "Ayur Herbal Shampoo", "description": "Gentle cleansing for hair", "price": 300, "image": "images/ayurherbal.jpg"},
    {"id": 6, "name": "Aloe Allen Juice", "description": "Detoxifying aloe vera juice", "price": 200, "image": "images/aloeallen.jpg"},
    {"id": 7, "name": "Eladi Oil", "description": "Traditional ayurvedic oil for skin", "price": 400, "image": "images/eladi.jpg"},
]

# ===== Login guard =====
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
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated

# ===== Default route: Redirect to login =====
@app.route("/")
def index():
    return redirect(url_for("login"))

# ===== Home Page =====
@app.route("/home")
@login_required
def home():
    return render_template("home.html", products=products)

# ===== Cart =====
@app.route('/add_to_cart/<product_name>', methods=['GET', 'POST'])
def add_to_cart(product_name):
    quantity = int(request.form.get('quantity', 1))

    # ✅ Search in Python list instead of DB
    product = next((p for p in products if p['name'] == product_name), None)

    if product:
        cart = session.get('cart', [])
        for item in cart:
            if item['name'] == product_name:
                item['quantity'] += quantity
                break
        else:
            cart.append({
                'name': product['name'],
                'price': product['price'],
                'image': product['image'],
                'quantity': quantity
            })
        session['cart'] = cart
        session.modified = True

    return redirect(url_for('products_page'))

@app.route("/cart")
@login_required
def cart():
    cart_items = session.get("cart", [])
    total = sum(float(item.get("price",0)) * item.get("quantity",1) for item in cart_items)
    return render_template("cart.html", cart_items=cart_items, total=total)

@app.route('/update_cart/<product_name>', methods=['POST'])
def update_cart(product_name):
    new_quantity = int(request.form.get('quantity', 1))
    cart = session.get('cart', [])

    for item in cart:
        if item['name'] == product_name:
            item['quantity'] = new_quantity
            break

    session['cart'] = cart
    flash(f'Quantity for {product_name} updated!', 'success')
    return redirect(url_for('cart'))

@app.route('/remove_from_cart/<string:product_name>')
@login_required
def remove_from_cart(product_name):
    cart = session.get('cart', [])
    cart = [item for item in cart if item['name'] != product_name]
    session['cart'] = cart
    session.modified = True
    return redirect(url_for('cart'))
@app.route("/clear_cart")
@login_required
def clear_cart():
    session["cart"] = []
    session.modified = True
    flash("All items removed from cart.", "info")
    return redirect(url_for("cart"))

# ===== Place Order =====
@app.route("/checkout", methods=["GET", "POST"])
@login_required
def checkout():
    if request.method == "POST":
        cart = session.get("cart", [])
        if not cart:
            flash("Your cart is empty!", "danger")
            return redirect(url_for("cart"))

        orders = load_orders()
        new_order = {
            "user": session["user_name"],
            "items": cart,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        orders.append(new_order)
        save_orders(orders)
        session["cart"] = []
        flash("Order placed successfully!", "success")
        return redirect(url_for("home"))

    # ✅ Pass cart items to checkout page
    cart = session.get("cart", [])
    return render_template("checkout.html", cart=cart)


# ===== Admin View Orders =====
@app.route("/admin/orders")
@admin_required
def view_orders():
    return render_template("orders.html", orders=load_orders())

# ===== Register =====
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

        con = get_db()
        cur = con.cursor()
        try:
            cur.execute(
                "INSERT INTO users (name, email, phone, password) VALUES (?, ?, ?, ?)",
                (name, email, phone, hashed_pw),
            )
            con.commit()
            flash("Registration successful! Please login.", "success")
            return redirect(url_for("login"))
        except sqlite3.IntegrityError:
            flash("Email already exists. Try logging in.", "danger")
        finally:
            con.close()

    return render_template("register.html")

# ===== Login =====
@app.route("/login", methods=["GET", "POST"])
def login():
    # Redirect already logged-in users
    if session.get("user_id"):
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        if not email or not password:
            flash("Please enter both email and password.", "warning")
            return render_template("login.html")

        try:
            con = get_db()
            cur = con.cursor()
            cur.execute("SELECT id, name, email, phone, password FROM users WHERE email=?", (email,))
            user = cur.fetchone()
        except Exception as e:
            flash("Database error. Please try again.", "danger")
            print("DB error:", e)
            return render_template("login.html")
        finally:
            con.close()

        if user:
            stored_hash = user[4]
            if isinstance(stored_hash, str):
                stored_hash = stored_hash.encode("utf-8")

            if bcrypt.checkpw(password.encode("utf-8"), stored_hash):
                # Successful login
                session["user_id"] = user[0]
                session["user_name"] = user[1]
                flash("Login successful!", "success")
                return redirect(url_for("home"))
            else:
                flash("Invalid email or password.", "danger")
        else:
            flash("Invalid email or password.", "danger")

    # GET request or failed POST
    # Ensure session keys used in template exist
    if "cart" not in session:
        session["cart"] = []
    print("Session contents:", dict(session))

    return render_template("login.html")



@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for("login"))

# ===== Forgot Password =====
@app.route("/forgot_password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        con = get_db()
        cur = con.cursor()
        cur.execute("SELECT id FROM users WHERE email=?", (email,))
        user = cur.fetchone()
        con.close()

        if user:
            token = s.dumps(email, salt="password-reset-salt")
            reset_url = url_for("reset_password", token=token, _external=True)

            msg = Message("Password Reset Request", recipients=[email])
            msg.body = f"To reset your password, click the link: {reset_url}\nIf you did not request this, ignore this email."
            mail.send(msg)

        flash("If an account with that email exists, a reset link has been sent.", "info")
        return redirect(url_for("login"))

    return render_template("forgot_password.html")

# ===== Reset Password =====
@app.route("/reset_password/<token>", methods=["GET", "POST"])
def reset_password(token):
    try:
        email = s.loads(token, salt="password-reset-salt", max_age=3600)
    except (SignatureExpired, BadSignature):
        flash("Invalid or expired token.", "danger")
        return redirect(url_for("forgot_password"))

    if request.method == "POST":
        new_password = request.form.get("password", "")
        hashed_pw = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt())

        con = get_db()
        cur = con.cursor()
        cur.execute("UPDATE users SET password=? WHERE email=?", (hashed_pw, email))
        con.commit()
        con.close()

        flash("Your password has been reset successfully!", "success")
        return redirect(url_for("login"))

    return render_template("reset_password.html")

# ===== Products Page =====
@app.route("/products")
@login_required
def products_page():
    return render_template("products.html", products=products)

# ===== Contact Page =====
@app.route("/contact")
@login_required
def contact():
    return render_template("contact.html")


@app.route("/send_message", methods=["POST"])
def send_message():
    name = request.form.get("name")
    email = request.form.get("email")
    message = request.form.get("message")

    if not name or not email or not message:
        flash("All fields are required.", "danger")
        return redirect(url_for("contact"))

    con = get_db()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO contact_messages (name, email, message, created_at)
        VALUES (?, ?, ?, datetime('now'))
    """, (name, email, message))
    con.commit()
    con.close()

    flash("Your message has been saved successfully!", "success")
    return redirect(url_for("contact"))
  # Redirect back to contact page

@app.route("/messages")
def messages():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT * FROM contact_messages ORDER BY created_at DESC")
    all_messages = cur.fetchall()
    con.close()
    return render_template("messages.html", messages=all_messages)

@app.route("/view_messages")
def view_messages():
    con = get_db()
    cur = con.cursor()
    cur.execute("SELECT * FROM contact_messages ORDER BY created_at DESC")
    messages = cur.fetchall()
    con.close()
    return render_template("view_messages.html", messages=messages)




# ===== Admin Dashboard =====
@app.route("/admin_dashboard")
@login_required
@admin_required
def admin_dashboard():
    if session.get("user_name") != "Admin":
        flash("Access denied!", "danger")
        return redirect(url_for("home"))

    search_query = request.args.get("search", "").strip().lower()

    con = get_db()
    cur = con.cursor()

    # Total orders
    cur.execute("SELECT COUNT(*) FROM orders")
    total_orders = cur.fetchone()[0]

    # Total revenue
    cur.execute("SELECT SUM(total) FROM orders")
    total_revenue = cur.fetchone()[0] or 0

    # Most active users
    cur.execute("""
        SELECT user_name, COUNT(*) as orders_count
        FROM orders
        GROUP BY user_id
        ORDER BY orders_count DESC
        LIMIT 5
    """)
    top_users = cur.fetchall()

    # Recent 5 or filtered orders
    if search_query:
        cur.execute("""
            SELECT * FROM orders
            WHERE LOWER(customer_name) LIKE ? OR LOWER(email) LIKE ?
            ORDER BY date DESC
        """, (f"%{search_query}%", f"%{search_query}%"))
    else:
        cur.execute("""
        SELECT customer_name, email, phone, address, total, date
        FROM orders
        ORDER BY date DESC
        LIMIT 5
        """)
    recent_orders = cur.fetchall()

        

    # ✅ Fetch recent 10 login logs
    cur.execute("""
        SELECT user_name, email, login_time
        FROM login_log
        ORDER BY login_time DESC
        LIMIT 10
    """)
    recent_logins = cur.fetchall()

    con.close()

    return render_template(
        "admin_dashboard.html",
        total_orders=total_orders,
        total_revenue=total_revenue,
        top_users=top_users,
        recent_orders=recent_orders,
        recent_logins=recent_logins  # ✅ pass to template
    )

@app.route("/admin_recent_logins")
@login_required
@admin_required
def admin_recent_logins():
    if session.get("user_name") != "Admin":
        flash("Access denied!", "danger")
        return redirect(url_for("home"))

    con = get_db()
    cur = con.cursor()

    # Fetch all recent logins (latest 50 for performance)
    cur.execute("""
        SELECT user_name, email, login_time
        FROM login_log
        ORDER BY login_time DESC
        LIMIT 50
    """)
    recent_logins = cur.fetchall()
    con.close()

    return render_template("admin_recent_logins.html", recent_logins=recent_logins)



# ===== Admin Clear Orders =====
@app.route("/admin_clear_orders", methods=["POST"])
@login_required
@admin_required
def admin_clear_orders():
    con = get_db()
    cur = con.cursor()
    cur.execute("DELETE FROM orders")
    con.commit()
    con.close()

    flash("All orders have been cleared!", "success")
    return redirect(url_for("admin_dashboard"))

@app.route('/test-email')
def test_email():
    msg = Message('Hello from Flask', recipients=['your_other_email@gmail.com'])
    msg.body = 'This is a test email from Flask-Mail using App Password.'
    mail.send(msg)
    return 'Email sent successfully!'

@app.route("/search")
@login_required
def search():
    query = request.args.get("query", "").lower().strip()
    if not query:
        return render_template("products.html", products=products)
    filtered = [p for p in products if query in p["name"].lower() or query in p["description"].lower()]
    return render_template("products.html", products=filtered)

@app.route("/buy_now", methods=["POST"])
def buy_now():
    product_name = request.form.get("product_name")
    try:
        quantity = int(request.form.get("quantity", 1))
    except (TypeError, ValueError):
        quantity = 1

    # Try to fetch from DB (using named columns)
    con = get_db()
    cur = con.cursor()
    try:
        cur.execute("SELECT id, name, price, image, description FROM products WHERE name=?", (product_name,))
        row = cur.fetchone()
    except Exception as e:
        row = None
    con.close()

    product_data = None

    if row:
        # row behaves like a dict thanks to Row factory
        # make sure price is numeric
        raw_price = row["price"]
        try:
            price = float(raw_price)
        except Exception:
            # best-effort parse (fallback to 0.0 if nothing numeric)
            import re
            m = re.search(r"[\d.]+", str(raw_price))
            price = float(m.group()) if m else 0.0

        product_data = {
            "id": row["id"],
            "name": row["name"],
            "price": price,
            "image": row["image"] or "",
            "description": row["description"] or "",
            "quantity": quantity
        }
    else:
        # Fallback: look up in in-memory products list (if you still use it)
        prod = next((p for p in products if p["name"] == product_name), None)
        if prod:
            product_data = {
                "id": prod.get("id"),
                "name": prod["name"],
                "price": float(prod["price"]),
                "image": prod.get("image",""),
                "description": prod.get("description",""),
                "quantity": quantity
            }

    if not product_data:
        flash("Product not found!", "danger")
        return redirect(url_for("products_page"))

    # Debugging (optional): uncomment to print to console
    # print("DEBUG product_data:", product_data)

    return render_template("checkout.html", product=product_data)



@app.route("/place-order", methods=["POST"])
@login_required
def place_order():
    # ✅ Step 1: Check OTP verification before proceeding
    if not session.get('otp_verified'):
        flash("Please verify OTP before placing the order.", "danger")
        return redirect(url_for('checkout'))  # Redirect back to checkout page

    # ✅ Step 2: Get form data
    product_name = request.form.get("product_name", "")
    quantity = int(request.form.get("quantity", 1))
    product_price = float(request.form.get("product_price", 0))
    customer_name = request.form.get("customer_name", "")
    email = request.form.get("email", "")
    phone = request.form.get("phone", "")
    address = request.form.get("address", "")
    payment = request.form.get("payment_method", "")

     # ✅ Handle product details safely
    product_name = request.form.get('product_name', 'Cart Items')
    
    quantity_str = request.form.get('quantity', '1')
    try:
        quantity = int(quantity_str)
    except ValueError:
        quantity = 1
    
    # ✅ Handle price safely
    price_str = request.form.get('product_price', '0')
    try:
        price = float(price_str)
    except ValueError:
        price = 0.0

    total = quantity * price

    # ✅ Step 3: Build items list and calculate total
    items = []
    if product_name == "Cart Items":
        for it in session.get("cart", []):
            items.append({
                "name": it.get("name"),
                "price": float(it.get("price", 0)),
                "quantity": it.get("quantity", 1)
            })
        total_amount = sum(i["price"] * i["quantity"] for i in items)
    else:
        price_num = float(product_price)
        items.append({"name": product_name, "price": price_num, "quantity": quantity})
        total_amount = price_num * quantity

    # ✅ Step 4: Save order in DB
    con = get_db()
    cur = con.cursor()
    cur.execute("""
        INSERT INTO orders (user_id, user_name, customer_name, email, phone, address, payment_method, items, quantity, total, date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session.get("user_id"),
        session.get("user_name"),
        customer_name,
        email,
        phone,
        address,
        payment,
        json.dumps(items),  # Save items as JSON
        sum(i.get("quantity", 1) for i in items),
        total_amount,
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ))
    con.commit()
    con.close()

    # ✅ Step 5: Clear cart and OTP session
    session["cart"] = []
    session.pop("otp_verified", None)  # Remove verification status
    session.modified = True

    flash("Order placed successfully!", "success")
    return redirect(url_for("thank_you"))



@app.route("/thank_you")
@login_required
def thank_you():
    return render_template("thank_you.html")

@app.route('/send-otp', methods=['POST'])
def send_otp():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'success': False, 'message': 'Email is required'}), 400

    # Cooldown check (30 sec)
    last_otp_time = session.get('otp_time', 0)
    if time.time() - last_otp_time < 30:
        return jsonify({'success': False, 'message': 'Please wait before requesting a new OTP.'}), 429

    otp = str(random.randint(100000, 999999))
    session['otp'] = otp
    session['email'] = email
    session['otp_time'] = time.time()
    session['otp_verified'] = False

    # Email configuration
    sender_email = "krishnakudre.1205@gmail.com"
    sender_password = "ucrx pejy shxv pkmg"  # Gmail App Password
    subject = "Your OTP for AyurvedaStore"
    body = f"Your OTP is {otp}. Do not share it."

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = sender_email
    msg['To'] = email

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, email, msg.as_string())

        return jsonify({'success': True, 'message': 'OTP sent to your email.'})

    except Exception as e:
        return jsonify({'success': False, 'message': f'Failed to send OTP: {str(e)}'}), 500


@app.route('/verify-otp', methods=['POST'])
def verify_otp():
    data = request.get_json()
    user_otp = data.get('otp')

    if not user_otp:
        return jsonify({'success': False, 'message': 'OTP is required'}), 400

    # Check OTP expiry (5 mins)
    otp_time = session.get('otp_time')
    if not otp_time or time.time() - otp_time > 300:
        return jsonify({'success': False, 'message': 'OTP expired. Please request a new one.'}), 400

    # Verify OTP
    if user_otp == session.get('otp'):
        session['otp_verified'] = True
        return jsonify({'success': True, 'message': 'OTP verified successfully.'})
    else:
        return jsonify({'success': False, 'message': 'Invalid OTP. Try again.'}), 400






@app.route("/thanks")
def thanks():
    return render_template("thanks.html")






if __name__ == "__main__":
    app.run(debug=True, port=5000)



