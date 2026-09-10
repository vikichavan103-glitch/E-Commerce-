import sqlite3
from flask import Flask, render_template_string, request, redirect, url_for, session, flash

app = Flask(__name__)
app.secret_key = "ecommerce_secret_key"
DB_NAME = "shop.db"

# --- 1. Database Setup ---
def get_db():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    
    # Products table
    c.execute("""
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        price INTEGER NOT NULL,
        image_url TEXT NOT NULL,
        description TEXT NOT NULL
    )""")

    # Orders table
    c.execute("""
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        phone TEXT NOT NULL,
        address TEXT NOT NULL,
        payment_method TEXT NOT NULL,
        items TEXT NOT NULL,
        total INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )""")

    # Seed initial products if database is empty
    c.execute("SELECT COUNT(*) FROM products")
    if c.fetchone()[0] == 0:
        sample_products = [
            ("iPhone 15 Pro", "Mobile", 119999, "https://images.unsplash.com/photo-1695048133142-1a20484d2569?w=500", "Titanium design with A17 Pro chip and 48MP camera."),
            ("Samsung Galaxy S24", "Mobile", 89999, "https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?w=500", "AI powered smartphone with Dynamic AMOLED 2X display."),
            ("MacBook Air M2", "Laptop", 99999, "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=500", "Supercharged by M2, 13.6-inch Liquid Retina display."),
            ("Sony WH-1000XM5", "Audio", 24999, "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?w=500", "Industry-leading active noise cancelling wireless headphones."),
            ("Apple Watch Series 9", "Wearable", 41999, "https://images.unsplash.com/photo-1523275335684-37898b6baf30?w=500", "Advanced health sensors, ECG, and bright always-on display."),
            ("Nike Air Max", "Fashion", 7999, "https://images.unsplash.com/photo-1542291026-7eec264c27ff?w=500", "Comfortable everyday running and training sneakers.")
        ]
        c.executemany("INSERT INTO products (name, category, price, image_url, description) VALUES (?, ?, ?, ?, ?)", sample_products)
        conn.commit()

    conn.close()

init_db()

# --- 2. Simple AI Recommendation Helper ---
def get_recommendations(category, current_id):
    conn = get_db()
    # Content-based: Recommend products in the same category
    recs = conn.execute("SELECT * FROM products WHERE category = ? AND id != ? LIMIT 3", (category, current_id)).fetchall()
    if not recs:
        recs = conn.execute("SELECT * FROM products WHERE id != ? LIMIT 3", (current_id,)).fetchall()
    conn.close()
    return recs

# --- 3. HTML Template ---
HTML_LAYOUT = """
<!DOCTYPE html>
<html>
<head>
    <title>EasyShop | E-Commerce</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.1/font/bootstrap-icons.css">
    <style>
        body { background: #f8f9fa; font-family: system-ui, sans-serif; }
        .card { border-radius: 12px; transition: transform 0.2s; }
        .card:hover { transform: translateY(-3px); }
        .card-img-top { height: 180px; object-fit: cover; }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark py-3">
        <div class="container">
            <a class="navbar-brand fw-bold" href="/"><i class="bi bi-shop me-1 text-warning"></i> EasyShop</a>
            <div class="d-flex align-items-center gap-3">
                <form class="d-flex" action="/" method="GET">
                    <input class="form-control form-control-sm me-2" name="q" placeholder="Search..." value="{{ request.args.get('q', '') }}">
                    <button class="btn btn-outline-light btn-sm" type="submit">Search</button>
                </form>
                <a href="/cart" class="btn btn-warning btn-sm fw-bold">
                    <i class="bi bi-cart"></i> Cart ({{ cart_count }})
                </a>
                <a href="/admin" class="btn btn-outline-light btn-sm">Admin</a>
            </div>
        </div>
    </nav>

    <div class="container my-4">
        {% with messages = get_flashed_messages() %}
            {% if messages %}
                {% for msg in messages %}
                    <div class="alert alert-info alert-dismissible fade show">{{ msg }}<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>
                {% endfor %}
            {% endif %}
        {% endwith %}

        {{ content|safe }}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""

# --- 4. Routes & Controllers ---

@app.context_processor
def cart_counter():
    cart = session.get("cart", {})
    return dict(cart_count=sum(cart.values()))

@app.route("/")
def index():
    query = request.args.get("q", "").strip()
    conn = get_db()
    if query:
        products = conn.execute("SELECT * FROM products WHERE name LIKE ? OR category LIKE ?", (f"%{query}%", f"%{query}%")).fetchall()
    else:
        products = conn.execute("SELECT * FROM products").fetchall()
    conn.close()

    content = f"""
    <div class="p-4 bg-primary text-white rounded-3 mb-4 shadow-sm">
        <h2 class="fw-bold">Welcome to EasyShop</h2>
        <p class="mb-0">Simple, clean, and modern Python E-Commerce website.</p>
    </div>

    <h4 class="fw-bold mb-3">Our Products</h4>
    <div class="row g-4">
        {"".join([f'''
        <div class="col-md-4 col-sm-6">
            <div class="card h-100 shadow-sm border-0">
                <img src="{p['image_url']}" class="card-img-top">
                <div class="card-body d-flex flex-column">
                    <span class="badge bg-secondary mb-1 align-self-start">{p['category']}</span>
                    <h5 class="fw-bold"><a href="/product/{p['id']}" class="text-dark text-decoration-none">{p['name']}</a></h5>
                    <p class="text-muted small text-truncate">{p['description']}</p>
                    <div class="mt-auto d-flex justify-content-between align-items-center">
                        <span class="fs-5 fw-bold text-primary">₹{p['price']:,}</span>
                        <a href="/add-to-cart/{p['id']}" class="btn btn-sm btn-primary"><i class="bi bi-cart-plus"></i> Add</a>
                    </div>
                </div>
            </div>
        </div>''' for p in products]) if products else '<p class="text-muted">No products found.</p>'}
    </div>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/product/<int:product_id>")
def product_detail(product_id):
    conn = get_db()
    product = conn.execute("SELECT * FROM products WHERE id = ?", (product_id,)).fetchone()
    if not product:
        conn.close()
        return "Product not found", 404
    
    recs = get_recommendations(product["category"], product_id)
    conn.close()

    content = f"""
    <div class="card shadow-sm border-0 p-4 mb-4">
        <div class="row g-4 align-items-center">
            <div class="col-md-5 text-center">
                <img src="{product['image_url']}" class="img-fluid rounded" style="max-height: 250px;">
            </div>
            <div class="col-md-7">
                <span class="badge bg-primary mb-2">{product['category']}</span>
                <h3 class="fw-bold">{product['name']}</h3>
                <h4 class="text-primary fw-bold my-3">₹{product['price']:,}</h4>
                <p class="text-muted">{product['description']}</p>
                <a href="/add-to-cart/{product['id']}" class="btn btn-primary btn-lg"><i class="bi bi-cart-plus"></i> Add to Cart</a>
            </div>
        </div>
    </div>

    <h5 class="fw-bold mb-3"><i class="bi bi-stars text-warning"></i> You May Also Like (AI Recommendations)</h5>
    <div class="row g-3">
        {"".join([f'''
        <div class="col-md-4">
            <div class="card shadow-sm border-0 p-2 d-flex flex-row align-items-center gap-3">
                <img src="{r['image_url']}" style="width: 70px; height: 70px; object-fit: cover; border-radius: 8px;">
                <div>
                    <h6 class="fw-bold mb-1"><a href="/product/{r['id']}" class="text-dark text-decoration-none">{r['name']}</a></h6>
                    <span class="text-primary fw-bold">₹{r['price']:,}</span>
                </div>
            </div>
        </div>''' for r in recs])}
    </div>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/add-to-cart/<int:product_id>")
def add_to_cart(product_id):
    cart = session.get("cart", {})
    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    session["cart"] = cart
    flash("Product added to cart!")
    return redirect(url_for("view_cart"))

@app.route("/remove-from-cart/<int:product_id>")
def remove_from_cart(product_id):
    cart = session.get("cart", {})
    cart.pop(str(product_id), None)
    session["cart"] = cart
    flash("Item removed from cart.")
    return redirect(url_for("view_cart"))

@app.route("/cart")
def view_cart():
    cart = session.get("cart", {})
    conn = get_db()
    items = []
    total = 0
    for pid, qty in cart.items():
        p = conn.execute("SELECT * FROM products WHERE id = ?", (int(pid),)).fetchone()
        if p:
            subtotal = p["price"] * qty
            total += subtotal
            items.append({"id": p["id"], "name": p["name"], "price": p["price"], "qty": qty, "subtotal": subtotal, "image": p["image_url"]})
    conn.close()

    content = f"""
    <h3 class="fw-bold mb-3"><i class="bi bi-cart3"></i> Your Cart</h3>
    {f'''
    <div class="row g-4">
        <div class="col-md-8">
            <div class="card shadow-sm border-0 p-3">
                {"".join([f"""
                <div class="d-flex justify-content-between align-items-center py-2 border-bottom">
                    <div class="d-flex align-items-center gap-3">
                        <img src="{i['image']}" style="width: 50px; height: 50px; object-fit: cover; border-radius: 6px;">
                        <div>
                            <h6 class="mb-0 fw-bold">{i['name']}</h6>
                            <small class="text-muted">₹{i['price']:,} × {i['qty']}</small>
                        </div>
                    </div>
                    <div class="text-end">
                        <span class="fw-bold me-3">₹{i['subtotal']:,}</span>
                        <a href="/remove-from-cart/{i['id']}" class="text-danger"><i class="bi bi-trash"></i></a>
                    </div>
                </div>""" for i in items])}
            </div>
        </div>
        <div class="col-md-4">
            <div class="card shadow-sm border-0 p-3">
                <h5 class="fw-bold">Total: <span class="text-primary">₹{total:,}</span></h5>
                <a href="/checkout" class="btn btn-primary w-100 mt-3 fw-bold">Proceed to Checkout</a>
            </div>
        </div>
    </div>''' if items else '<div class="alert alert-secondary text-center">Your cart is currently empty. <a href="/">Shop Now</a></div>'}
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", {})
    if not cart:
        return redirect(url_for("index"))

    conn = get_db()
    items_list = []
    total = 0
    for pid, qty in cart.items():
        p = conn.execute("SELECT * FROM products WHERE id = ?", (int(pid),)).fetchone()
        if p:
            subtotal = p["price"] * qty
            total += subtotal
            items_list.append(f"{p['name']} (x{qty})")

    if request.method == "POST":
        name = request.form["name"]
        phone = request.form["phone"]
        address = request.form["address"]
        payment = request.form["payment"]
        items_str = ", ".join(items_list)

        # Save order into SQLite database
        conn.execute("INSERT INTO orders (name, phone, address, payment_method, items, total) VALUES (?, ?, ?, ?, ?, ?)",
                     (name, phone, address, payment, items_str, total))
        conn.commit()
        conn.close()

        # Clear cart
        session["cart"] = {}
        flash("Order placed successfully! Thank you for shopping.")
        return redirect(url_for("index"))

    conn.close()
    content = f"""
    <div class="row justify-content-center">
        <div class="col-md-6">
            <div class="card shadow-sm border-0 p-4">
                <h4 class="fw-bold mb-3"><i class="bi bi-credit-card"></i> Checkout</h4>
                <form method="POST">
                    <div class="mb-2"><label class="small fw-bold">Your Name</label><input class="form-control" name="name" required></div>
                    <div class="mb-2"><label class="small fw-bold">Phone Number</label><input class="form-control" name="phone" required></div>
                    <div class="mb-2"><label class="small fw-bold">Delivery Address</label><textarea class="form-control" name="address" required></textarea></div>
                    <div class="mb-3">
                        <label class="small fw-bold">Payment Method</label>
                        <select class="form-select" name="payment"><option value="UPI">UPI / Google Pay</option><option value="Card">Debit / Credit Card</option><option value="COD">Cash on Delivery</option></select>
                    </div>
                    <div class="d-flex justify-content-between mb-3"><span class="fw-bold">Total to Pay:</span><span class="fs-5 fw-bold text-primary">₹{total:,}</span></div>
                    <button type="submit" class="btn btn-primary w-100 fw-bold">Confirm Order</button>
                </form>
            </div>
        </div>
    </div>
    """
    return render_template_string(HTML_LAYOUT, content=content)

@app.route("/admin")
def admin():
    conn = get_db()
    orders = conn.execute("SELECT * FROM orders ORDER BY id DESC").fetchall()
    total_sales = conn.execute("SELECT COALESCE(SUM(total), 0) FROM orders").fetchone()[0]
    conn.close()

    content = f"""
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h3 class="fw-bold mb-0"><i class="bi bi-speedometer2"></i> Admin Panel</h3>
        <span class="badge bg-success fs-6">Total Sales: ₹{total_sales:,}</span>
    </div>
    <div class="card shadow-sm border-0 p-3">
        <h5 class="fw-bold mb-3">Customer Orders ({len(orders)})</h5>
        <div class="table-responsive">
            <table class="table table-bordered table-striped small align-middle">
                <thead class="table-dark">
                    <tr><th>#ID</th><th>Customer</th><th>Phone</th><th>Address</th><th>Items</th><th>Total</th><th>Payment</th></tr>
                </thead>
                <tbody>
                    {"".join([f"<tr><td>#{o['id']}</td><td><b>{o['name']}</b></td><td>{o['phone']}</td><td>{o['address']}</td><td>{o['items']}</td><td><b>₹{o['total']:,}</b></td><td>{o['payment_method']}</td></tr>" for o in orders]) if orders else '<tr><td colspan="7" class="text-center">No orders received yet.</td></tr>'}
                </tbody>
            </table>
        </div>
    </div>
    """
    return render_template_string(HTML_LAYOUT, content=content)

if __name__ == "__main__":
    print("=" * 45)
    print(" EasyShop Server Running: http://127.0.0.1:5000")
    print("=" * 45)
    app.run(host="0.0.0.0", port=5000, debug=True)
