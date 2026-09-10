import os
import re
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from database import init_db
import models
from recommender import recommender

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'novamart_ecommerce_secret_key_2026')

# Initialize database schema and initial seed data on startup
init_db()

# ----------------- Decorators & Helpers ----------------- #

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            flash('Please log in to continue.', 'warning')
            return redirect(url_for('login', next=request.path))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or session.get('role') != 'admin':
            flash('Access denied. Administrator privileges required.', 'danger')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function

@app.context_processor
def inject_global_data():
    """Provides navigation categories and live cart item count to all templates."""
    categories = models.get_all_categories()
    cart_count = 0
    
    if 'user_id' in session:
        items, _ = models.get_cart_items_for_user(user_id=session['user_id'])
        cart_count = sum(i['quantity'] for i in items)
    else:
        session_cart = session.get('cart', {})
        cart_count = sum(session_cart.values())

    return dict(nav_categories=categories, cart_count=cart_count)

def slugify(text):
    return re.sub(r'[\W_]+', '-', text.lower()).strip('-')

# ----------------- Public Customer Routes ----------------- #

@app.route('/')
def index():
    featured = models.get_featured_products(limit=8)
    user_id = session.get('user_id')
    ai_recs = recommender.get_user_recommendations(user_id=user_id, top_n=4)
    return render_template('index.html', featured_products=featured, ai_recommendations=ai_recs)

@app.route('/products')
def products():
    category_slug = request.args.get('category')
    search_query = request.args.get('q')
    max_price = request.args.get('max_price')
    sort_by = request.args.get('sort', 'featured')

    current_cat = None
    if category_slug:
        current_cat = models.get_category_by_slug(category_slug)

    product_list = models.get_all_products(
        category_slug=category_slug,
        search_query=search_query,
        max_price=max_price,
        sort_by=sort_by
    )

    return render_template(
        'products.html',
        products=product_list,
        current_category=category_slug,
        current_category_obj=current_cat,
        search_query=search_query,
        max_price=max_price,
        sort_by=sort_by
    )

@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = models.get_product_by_id(product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products'))

    reviews = models.get_reviews_for_product(product_id)
    similar_prods = recommender.get_similar_products(product_id, top_n=4)
    frequently_bought = recommender.get_frequently_bought_together(product_id, top_n=3)

    return render_template(
        'product_detail.html',
        product=product,
        reviews=reviews,
        similar_products=similar_prods,
        frequently_bought=frequently_bought
    )

@app.route('/product/<int:product_id>/review', methods=['POST'])
@login_required
def add_review(product_id):
    rating = int(request.form.get('rating', 5))
    comment = request.form.get('comment', '').strip()

    if not comment:
        flash('Review comment cannot be empty.', 'warning')
        return redirect(url_for('product_detail', product_id=product_id))

    models.add_review(product_id, session['user_id'], rating, comment)
    flash('Thank you! Your review has been submitted successfully.', 'success')
    return redirect(url_for('product_detail', product_id=product_id))

# ----------------- Cart & Checkout Routes ----------------- #

@app.route('/cart')
def view_cart():
    user_id = session.get('user_id')
    session_cart = session.get('cart', {})
    cart_items, total_amount = models.get_cart_items_for_user(user_id=user_id, session_cart=session_cart)
    return render_template('cart.html', cart_items=cart_items, total_amount=total_amount)

@app.route('/add_to_cart/<int:product_id>')
def add_to_cart(product_id):
    product = models.get_product_by_id(product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products'))

    if 'user_id' in session:
        models.add_to_cart_db(session['user_id'], product_id, quantity=1)
    else:
        cart = session.get('cart', {})
        cart[str(product_id)] = cart.get(str(product_id), 0) + 1
        session['cart'] = cart

    flash(f"'{product['name']}' was added to your cart!", 'success')
    return redirect(request.referrer or url_for('view_cart'))

@app.route('/add_to_cart_custom/<int:product_id>', methods=['POST'])
def add_to_cart_custom(product_id):
    product = models.get_product_by_id(product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('products'))

    qty = int(request.form.get('quantity', 1))
    if qty <= 0:
        qty = 1

    if 'user_id' in session:
        models.add_to_cart_db(session['user_id'], product_id, quantity=qty)
    else:
        cart = session.get('cart', {})
        cart[str(product_id)] = cart.get(str(product_id), 0) + qty
        session['cart'] = cart

    flash(f"Added {qty} item(s) of '{product['name']}' to your cart.", 'success')
    return redirect(url_for('view_cart'))

@app.route('/buy_now/<int:product_id>')
def buy_now(product_id):
    add_to_cart(product_id)
    return redirect(url_for('checkout'))

@app.route('/cart/update/<int:product_id>', methods=['POST'])
def update_cart(product_id):
    qty = int(request.form.get('quantity', 1))
    if 'user_id' in session:
        models.update_cart_db(session['user_id'], product_id, qty)
    else:
        cart = session.get('cart', {})
        if qty <= 0 and str(product_id) in cart:
            del cart[str(product_id)]
        else:
            cart[str(product_id)] = qty
        session['cart'] = cart

    flash('Cart updated successfully.', 'info')
    return redirect(url_for('view_cart'))

@app.route('/cart/qty/<int:product_id>/<action>')
def update_cart_qty(product_id, action):
    if 'user_id' in session:
        items, _ = models.get_cart_items_for_user(user_id=session['user_id'])
        current_item = next((i for i in items if i['product_id'] == product_id), None)
        if current_item:
            new_qty = current_item['quantity'] + 1 if action == 'inc' else current_item['quantity'] - 1
            models.update_cart_db(session['user_id'], product_id, new_qty)
    else:
        cart = session.get('cart', {})
        curr = cart.get(str(product_id), 1)
        if action == 'inc':
            cart[str(product_id)] = curr + 1
        else:
            if curr > 1:
                cart[str(product_id)] = curr - 1
            else:
                cart.pop(str(product_id), None)
        session['cart'] = cart

    return redirect(url_for('view_cart'))

@app.route('/remove_from_cart/<int:product_id>')
def remove_from_cart(product_id):
    if 'user_id' in session:
        models.remove_from_cart_db(session['user_id'], product_id)
    else:
        cart = session.get('cart', {})
        cart.pop(str(product_id), None)
        session['cart'] = cart

    flash('Item removed from cart.', 'info')
    return redirect(url_for('view_cart'))

@app.route('/clear_cart')
def clear_cart():
    if 'user_id' in session:
        models.clear_cart_db(session['user_id'])
    session['cart'] = {}
    flash('Cart cleared.', 'info')
    return redirect(url_for('view_cart'))

@app.route('/checkout')
@login_required
def checkout():
    user_id = session.get('user_id')
    user = models.get_user_by_id(user_id)
    cart_items, total_amount = models.get_cart_items_for_user(user_id=user_id)

    if not cart_items:
        flash('Your cart is empty. Add products before checking out.', 'warning')
        return redirect(url_for('products'))

    return render_template('checkout.html', cart_items=cart_items, total_amount=total_amount, current_user=user)

@app.route('/checkout/process', methods=['POST'])
@login_required
def process_checkout():
    user_id = session.get('user_id')
    cart_items, total_amount = models.get_cart_items_for_user(user_id=user_id)

    if not cart_items:
        flash('Your cart is empty.', 'danger')
        return redirect(url_for('products'))

    shipping_info = {
        'name': request.form.get('shipping_name', '').strip(),
        'email': request.form.get('shipping_email', '').strip(),
        'phone': request.form.get('shipping_phone', '').strip(),
        'address': request.form.get('shipping_address', '').strip(),
    }
    payment_method = request.form.get('payment_method', 'UPI')

    if not all(shipping_info.values()):
        flash('Please fill in all shipping and delivery address details.', 'warning')
        return redirect(url_for('checkout'))

    # Execute ACID Transaction
    order_id, err = models.process_checkout_transaction(user_id, shipping_info, payment_method, cart_items, total_amount)
    
    if err:
        flash(f'Checkout error: {err}', 'danger')
        return redirect(url_for('view_cart'))

    # Clear guest session cart if any
    session['cart'] = {}

    flash('Order placed successfully! Transaction completed with ACID compliance.', 'success')
    return redirect(url_for('order_success', order_id=order_id))

@app.route('/order/success/<int:order_id>')
@login_required
def order_success(order_id):
    order, items = models.get_order_details(order_id)
    if not order:
        flash('Order not found.', 'danger')
        return redirect(url_for('index'))

    # Security check: User must own the order or be admin
    if order['user_id'] != session['user_id'] and session.get('role') != 'admin':
        flash('Unauthorized access to order invoice.', 'danger')
        return redirect(url_for('index'))

    return render_template('order_success.html', order=order, items=items)

@app.route('/my_orders')
@login_required
def my_orders():
    orders = models.get_orders_by_user(session['user_id'])
    return render_template('orders.html', orders=orders)

# ----------------- User Authentication ----------------- #

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        next_url = request.form.get('next') or request.args.get('next')

        user = models.get_user_by_email(email)
        if user and models.check_password_hash(user['password_hash'], password):
            session['user_id'] = user['id']
            session['name'] = user['name']
            session['email'] = user['email']
            session['role'] = user['role']

            # Sync guest session cart into DB cart
            if 'cart' in session:
                models.sync_session_cart_to_db(user['id'], session['cart'])

            flash(f"Welcome back, {user['name']}!", 'success')
            if user['role'] == 'admin':
                return redirect(url_for('admin_dashboard'))
            return redirect(next_url or url_for('index'))
        else:
            flash('Invalid email or password. Please try again.', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()

        if len(password) < 6:
            flash('Password must be at least 6 characters long.', 'warning')
            return render_template('register.html')

        user_id, err = models.create_user(name, email, password, phone, address, role='customer')
        if err:
            flash(err, 'danger')
            return render_template('register.html')

        # Auto-login newly registered user
        session['user_id'] = user_id
        session['name'] = name
        session['email'] = email
        session['role'] = 'customer'

        if 'cart' in session:
            models.sync_session_cart_to_db(user_id, session['cart'])

        flash('Registration successful! Welcome to NovaMart.', 'success')
        return redirect(url_for('index'))

    return render_template('register.html')

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out safely.', 'info')
    return redirect(url_for('index'))

@app.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user_id = session['user_id']
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        phone = request.form.get('phone', '').strip()
        address = request.form.get('address', '').strip()

        models.update_user_profile(user_id, name, phone, address)
        session['name'] = name
        flash('Profile details updated successfully.', 'success')
        return redirect(url_for('profile'))

    user = models.get_user_by_id(user_id)
    return render_template('profile.html', user=user)

# ----------------- Admin Management Routes ----------------- #

@app.route('/admin')
@admin_required
def admin_dashboard():
    metrics = models.get_admin_dashboard_metrics()
    return render_template('admin/dashboard.html', **metrics)

@app.route('/admin/products')
@admin_required
def admin_products():
    product_list = models.get_all_products(sort_by='newest')
    return render_template('admin/products.html', products=product_list)

@app.route('/admin/product/add', methods=['GET', 'POST'])
@admin_required
def admin_add_product():
    categories = models.get_all_categories()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = int(request.form.get('category_id'))
        price = float(request.form.get('price'))
        disc_price = request.form.get('discount_price')
        discount_price = float(disc_price) if disc_price else None
        stock = int(request.form.get('stock', 10))
        image_url = request.form.get('image_url', '').strip()
        description = request.form.get('description', '').strip()
        is_featured = 1 if request.form.get('is_featured') else 0
        slug = slugify(name)

        models.create_product(category_id, name, slug, description, price, discount_price, stock, image_url, is_featured)
        recommender.fit() # Refresh ML TF-IDF vectors
        flash(f"Product '{name}' added successfully!", 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin/product_form.html', categories=categories, product=None)

@app.route('/admin/product/edit/<int:product_id>', methods=['GET', 'POST'])
@admin_required
def admin_edit_product(product_id):
    product = models.get_product_by_id(product_id)
    if not product:
        flash('Product not found.', 'danger')
        return redirect(url_for('admin_products'))

    categories = models.get_all_categories()
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        category_id = int(request.form.get('category_id'))
        price = float(request.form.get('price'))
        disc_price = request.form.get('discount_price')
        discount_price = float(disc_price) if disc_price else None
        stock = int(request.form.get('stock', 10))
        image_url = request.form.get('image_url', '').strip()
        description = request.form.get('description', '').strip()
        is_featured = 1 if request.form.get('is_featured') else 0
        slug = slugify(name)

        models.update_product(product_id, category_id, name, slug, description, price, discount_price, stock, image_url, is_featured)
        recommender.fit() # Refresh ML TF-IDF vectors
        flash(f"Product '{name}' updated successfully!", 'success')
        return redirect(url_for('admin_products'))

    return render_template('admin/product_form.html', categories=categories, product=product)

@app.route('/admin/product/delete/<int:product_id>', methods=['POST'])
@admin_required
def admin_delete_product(product_id):
    models.delete_product(product_id)
    recommender.fit()
    flash('Product deleted from catalog.', 'info')
    return redirect(url_for('admin_products'))

@app.route('/admin/orders')
@admin_required
def admin_orders():
    order_list = models.get_all_orders_admin()
    return render_template('admin/orders.html', orders=order_list)

@app.route('/admin/orders/update/<int:order_id>', methods=['POST'])
@admin_required
def admin_update_order_status(order_id):
    new_status = request.form.get('status')
    models.update_order_status(order_id, new_status)
    flash(f"Order #{order_id} status updated to '{new_status}'.", 'success')
    return redirect(url_for('admin_orders'))

@app.route('/admin/users')
@admin_required
def admin_users():
    user_list = models.get_all_users()
    return render_template('admin/users.html', users=user_list)

# ----------------- Application Entry Point ----------------- #

if __name__ == '__main__':
    print('='*50)
    print('  NovaMart E-Commerce Platform Server Started')
    print('  Local URL: http://127.0.0.1:5000')
    print('  Admin Login: admin@ecommerce.com / admin123')
    print('  Customer Login: john@example.com / john123')
    print('='*50)
    app.run(host='0.0.0.0', port=5000, debug=True)
