from flask import Flask, render_template, request, redirect, url_for, session, flash
from functools import wraps
import sqlite3, bcrypt
import json, os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "your_secret_key"  # TODO: replace with a strong random value

DATABASE_PATH = os.path.join(app.root_path, "database.db")
ORDERS_FILE = os.path.join(app.root_path, "orders.json")


# ===== Database helpers =====
def get_db():
    """
    Return a sqlite3 connection with row factory (dict-like access)
    and foreign_keys enabled.
    """
    con = sqlite3.connect(DATABASE_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON;")
    return con


def init_db():
    with get_db() as con:
        cur = con.cursor()
        # users table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                phone TEXT,
                password BLOB NOT NULL
            )
        """)
        # orders table
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
                items TEXT,          -- JSON string of ordered items
                total REAL,
                date TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        """)
        # login_log table
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


# initialize DB
init_db()


# ===== File helpers (orders) =====
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
            return redirect(url_for("home"))
        return f(*args, **kwargs)
    return decorated


# ===== Auth: register / login / logout =====
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

        # Hash password
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

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    # Redirect if already logged in
    if session.get("user_id"):
        return redirect(url_for("home"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with get_db() as con:
            cur = con.cursor()
            cur.execute("SELECT id, name, email, phone, password FROM users WHERE email=?", (email,))
            user = cur.fetchone()

        # user will be a sqlite3.Row or None
        if user:
            stored_pw = user["password"]
            # stored_pw may be bytes (BLOB). bcrypt.checkpw expects bytes.
            try:
                if bcrypt.checkpw(password.encode("utf-8"), stored_pw):
                    # Set session
                    session["user_id"] = user["id"]
                    session["user_name"] = user["name"]

                    # Log the login event
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
                    return redirect(url_for("home"))
            except Exception:
                # If stored_pw is not bytes or checkpw fails for some reason
                flash("Authentication error. Please try again.", "danger")
                return redirect(url_for("login"))

        flash("Invalid email or password.", "danger")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    flash("Logged out successfully!", "info")
    return redirect(url_for("login"))


# ===== Public-facing routes =====
@app.route("/")
@login_required
def home():
    return render_template("home.html")


@app.route("/home")
@login_required
def home_alias():
    return redirect(url_for("home"))


@app.route("/products")
@login_required
def products_page():
    return render_template("products.html", products=products)


@app.route("/search")
@login_required
def search():
    query = request.args.get("query", "").lower().strip()
    if not query:
        return render_template("products.html", products=products)
    filtered = [p for p in products if query in p["name"].lower() or query in p["description"].lower()]
    return render_template("products.html", products=filtered)


@app.route("/add_to_cart/<product_name>")
@login_required
def add_to_cart(product_name):
    cart = session.get("cart", [])
    product = next((p for p in products if p["name"] == product_name), None)
    if product:
        cart.append(product)
        session["cart"] = cart
        session.modified = True
        flash(f"{product_name} added to cart!", "success")
    else:
        flash("Product not found.", "danger")
    return redirect(url_for("products_page"))


@app.route("/cart")
@login_required
def cart():
    cart_items = session.get("cart", [])
    total = sum(float(item.get("price", 0)) for item in cart_items)
    return render_template("cart.html", cart_items=cart_items, total=total)


@app.route("/clear_cart")
@login_required
def clear_cart():
    session["cart"] = []
    session.modified = True
    flash("All items removed from cart.", "info")
    return redirect(url_for("cart"))


@app.route("/remove_from_cart/<product_name>")
@login_required
def remove_from_cart(product_name):
    if "cart" in session:
        session["cart"] = [item for item in session["cart"] if item.get("name") != product_name]
        session.modified = True
        flash(f"{product_name} removed from cart!", "info")
    return redirect(url_for("cart"))


@app.route("/buy_now/<product_name>")
@login_required
def buy_now(product_name):
    product = next((p for p in products if p["name"] == product_name), None)
    if not product:
        return "Product not found", 404
    return render_template("checkout.html", product=product, cart_items=None, total=product["price"])


@app.route("/checkout")
@login_required
def checkout():
    cart_items = session.get("cart", [])
    if not cart_items:
        flash("Your cart is empty!", "warning")
        return redirect(url_for("products_page"))
    total = sum(float(item.get("price", 0)) for item in cart_items)
    return render_template("checkout.html", product=None, cart_items=cart_items, total=total)


@app.route("/place_order", methods=["POST"])
@login_required
def place_order():
    product_name = request.form.get("product_name", "")
    product_price = request.form.get("product_price", "0")
    customer_name = request.form.get("customer_name", "")
    email = request.form.get("email", "")
    phone = request.form.get("phone", "")
    address = request.form.get("address", "")
    payment = request.form.get("payment_method", "")

    items = []
    if product_name == "Cart Items":
        for it in session.get("cart", []):
            items.append({"name": it.get("name"), "price": float(it.get("price", 0))})
        total_amount = sum(i.get("price", 0) for i in items)
    else:
        try:
            price_num = float(product_price)
        except:
            price_num = 0.0
        items.append({"name": product_name, "price": price_num})
        total_amount = price_num

    with get_db() as con:
        cur = con.cursor()
        cur.execute("""
            INSERT INTO orders (user_id, user_name, customer_name, email, phone, address, payment_method, items, total, date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session.get("user_id"),
            session.get("user_name"),
            customer_name,
            email,
            phone,
            address,
            payment,
            json.dumps(items),
            float(total_amount),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ))
        con.commit()

    session["cart"] = []
    session.modified = True

    flash("Order placed successfully!", "success")
    return redirect(url_for("thank_you"))


@app.route("/thank_you")
@login_required
def thank_you():
    return render_template("thank_you.html")


@app.route("/contact")
@login_required
def contact():
    return render_template("contact.html")


# ===== Admin Orders & Dashboard =====
@app.route("/admin_orders")
@login_required
@admin_required
def admin_orders():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("SELECT * FROM orders ORDER BY date DESC")
        orders = cur.fetchall()

    orders_list = []
    for o in orders:
        # o is sqlite3.Row
        orders_list.append({
            "id": o["id"],
            "user_id": o["user_id"],
            "user_name": o["user_name"],
            "customer_name": o["customer_name"],
            "email": o["email"],
            "phone": o["phone"],
            "address": o["address"],
            "payment_method": o["payment_method"],
            "items": json.loads(o["items"]) if o["items"] else [],
            "total": o["total"],
            "date": o["date"]
        })

    return render_template("admin_orders.html", orders=orders_list)


@app.route("/admin_dashboard")
@login_required
@admin_required
def admin_dashboard():
    search_query = request.args.get("search", "").strip().lower()

    with get_db() as con:
        cur = con.cursor()

        # Total orders
        cur.execute("SELECT COUNT(*) as c FROM orders")
        total_orders = cur.fetchone()["c"] or 0

        # Total revenue
        cur.execute("SELECT SUM(total) as s FROM orders")
        total_revenue = cur.fetchone()["s"] or 0

        # Most active users - group by user_id and user_name
        cur.execute("""
            SELECT user_id, user_name, COUNT(*) as orders_count
            FROM orders
            GROUP BY user_id, user_name
            ORDER BY orders_count DESC
            LIMIT 5
        """)
        top_users = cur.fetchall()

        # Recent 5 orders (or filtered)
        if search_query:
            cur.execute("""
                SELECT * FROM orders
                WHERE LOWER(customer_name) LIKE ? OR LOWER(email) LIKE ?
                ORDER BY date DESC
            """, (f"%{search_query}%", f"%{search_query}%"))
            recent_orders = cur.fetchall()
        else:
            cur.execute("SELECT * FROM orders ORDER BY date DESC LIMIT 5")
            recent_orders = cur.fetchall()

        # RECENT LOGINS (last 5)
        cur.execute("SELECT user_id, user_name, email, login_time FROM login_log ORDER BY login_time DESC LIMIT 5")
        recent_logins = cur.fetchall()

    # render
    return render_template(
        "admin_dashboard.html",
        total_orders=total_orders,
        total_revenue=total_revenue,
        top_users=top_users,
        recent_orders=recent_orders,
        recent_logins=recent_logins
    )


@app.route("/admin_clear_orders", methods=["POST"])
@login_required
@admin_required
def admin_clear_orders():
    with get_db() as con:
        cur = con.cursor()
        cur.execute("DELETE FROM orders")
        con.commit()
    flash("All orders have been cleared!", "success")
    return redirect(url_for("admin_dashboard"))


@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()  # Check if email exists

        if user:
            # Generate a secure token valid for 30 minutes
            token = s.dumps(email, salt='password-reset-salt')

            # Build password reset link
            reset_link = url_for('reset_password', token=token, _external=True)

            # Send email
            msg = Message('Password Reset Request', recipients=[email])
            msg.body = f'Hello {user.name},\n\nClick the link below to reset your password:\n{reset_link}\n\nThis link will expire in 30 minutes.'
            mail.send(msg)

        flash('If your email exists in our system, a password reset link has been sent.', 'info')
        return redirect(url_for('login'))

    return render_template('forgot_password.html')


@app.route('/admin_logins')
@admin_required
def admin_logins():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("SELECT user_name, email, login_time FROM login_log ORDER BY login_time DESC")
    all_logins = cur.fetchall()
    conn.close()
    return render_template('admin_logins.html', all_logins=all_logins)

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    try:
        # Validate token and get email
        email = s.loads(token, salt='password-reset-salt', max_age=1800)  # 30 minutes
    except:
        flash('The password reset link is invalid or has expired.', 'danger')
        return redirect(url_for('forgot_password'))

    if request.method == 'POST':
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        user.password = hash_password(password)  # Hash the password properly
        db.session.commit()
        flash('Your password has been reset successfully!', 'success')
        return redirect(url_for('login'))

    return render_template('reset_password.html')




if __name__ == "__main__":
    app.run(debug=True, port=5001)


