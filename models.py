import sqlite3
import random
import datetime
from database import get_db_connection
from werkzeug.security import generate_password_hash, check_password_hash

# ----------------- User Authentication & Management ----------------- #

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return user

def get_user_by_email(email):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE LOWER(email) = LOWER(?)', (email.strip(),)).fetchone()
    conn.close()
    return user

def create_user(name, email, password, phone, address, role='customer'):
    conn = get_db_connection()
    cursor = conn.cursor()
    password_hash = generate_password_hash(password)
    try:
        cursor.execute('''
        INSERT INTO users (name, email, password_hash, phone, address, role)
        VALUES (?, ?, ?, ?, ?, ?)
        ''', (name.strip(), email.strip().lower(), password_hash, phone.strip(), address.strip(), role))
        conn.commit()
        user_id = cursor.lastrowid
        return user_id, None
    except sqlite3.IntegrityError:
        return None, 'An account with this email address already exists.'
    finally:
        conn.close()

def update_user_profile(user_id, name, phone, address):
    conn = get_db_connection()
    conn.execute('''
    UPDATE users SET name = ?, phone = ?, address = ? WHERE id = ?
    ''', (name.strip(), phone.strip(), address.strip(), user_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_db_connection()
    users = conn.execute('SELECT * FROM users ORDER BY created_at DESC').fetchall()
    conn.close()
    return users

# ----------------- Categories & Products ----------------- #

def get_all_categories():
    conn = get_db_connection()
    categories = conn.execute('SELECT * FROM categories ORDER BY name ASC').fetchall()
    conn.close()
    return categories

def get_category_by_slug(slug):
    conn = get_db_connection()
    cat = conn.execute('SELECT * FROM categories WHERE slug = ?', (slug,)).fetchone()
    conn.close()
    return cat

def get_all_products(category_slug=None, search_query=None, max_price=None, sort_by='featured'):
    conn = get_db_connection()
    
    query = '''
    SELECT p.*, c.name as category_name, c.slug as category_slug
    FROM products p
    JOIN categories c ON p.category_id = c.id
    WHERE 1=1
    '''
    params = []

    if category_slug:
        query += ' AND c.slug = ?'
        params.append(category_slug)

    if search_query:
        query += ' AND (p.name LIKE ? OR p.description LIKE ? OR c.name LIKE ?)'
        wildcard = f'%{search_query.strip()}%'
        params.extend([wildcard, wildcard, wildcard])

    if max_price:
        query += ' AND (COALESCE(p.discount_price, p.price) <= ?)'
        params.append(float(max_price))

    if sort_by == 'price_asc':
        query += ' ORDER BY COALESCE(p.discount_price, p.price) ASC'
    elif sort_by == 'price_desc':
        query += ' ORDER BY COALESCE(p.discount_price, p.price) DESC'
    elif sort_by == 'newest':
        query += ' ORDER BY p.id DESC'
    else:  # featured / top-rated
        query += ' ORDER BY p.is_featured DESC, p.rating DESC, p.id DESC'

    products = conn.execute(query, params).fetchall()
    conn.close()
    return products

def get_featured_products(limit=8):
    conn = get_db_connection()
    query = '''
    SELECT p.*, c.name as category_name, c.slug as category_slug
    FROM products p
    JOIN categories c ON p.category_id = c.id
    WHERE p.is_featured = 1 OR p.rating >= 4.7
    ORDER BY p.rating DESC, p.is_featured DESC
    LIMIT ?
    '''
    featured = conn.execute(query, (limit,)).fetchall()
    conn.close()
    return featured

def get_product_by_id(product_id):
    conn = get_db_connection()
    query = '''
    SELECT p.*, c.name as category_name, c.slug as category_slug
    FROM products p
    JOIN categories c ON p.category_id = c.id
    WHERE p.id = ?
    '''
    product = conn.execute(query, (product_id,)).fetchone()
    conn.close()
    return product

def create_product(category_id, name, slug, description, price, discount_price, stock, image_url, is_featured):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO products (category_id, name, slug, description, price, discount_price, stock, image_url, is_featured)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (category_id, name, slug, description, price, discount_price, stock, image_url, is_featured))
    conn.commit()
    pid = cursor.lastrowid
    conn.close()
    return pid

def update_product(product_id, category_id, name, slug, description, price, discount_price, stock, image_url, is_featured):
    conn = get_db_connection()
    conn.execute('''
    UPDATE products
    SET category_id = ?, name = ?, slug = ?, description = ?, price = ?, discount_price = ?,
        stock = ?, image_url = ?, is_featured = ?
    WHERE id = ?
    ''', (category_id, name, slug, description, price, discount_price, stock, image_url, is_featured, product_id))
    conn.commit()
    conn.close()

def delete_product(product_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM products WHERE id = ?', (product_id,))
    conn.commit()
    conn.close()

# ----------------- Cart Management ----------------- #

def get_cart_items_for_user(user_id=None, session_cart=None):
    """Fetches cart products with quantity and computes item subtotals and grand total."""
    conn = get_db_connection()
    items = []
    
    if user_id:
        query = '''
        SELECT ci.id as cart_item_id, ci.quantity, p.id as product_id, p.name, 
               COALESCE(p.discount_price, p.price) as unit_price, p.stock, p.image_url,
               c.name as category_name
        FROM cart_items ci
        JOIN products p ON ci.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        WHERE ci.user_id = ?
        '''
        rows = conn.execute(query, (user_id,)).fetchall()
        for r in rows:
            subtotal = r['unit_price'] * r['quantity']
            item_dict = dict(r)
            item_dict['subtotal'] = subtotal
            items.append(item_dict)
    elif session_cart:
        for pid, qty in session_cart.items():
            query = '''
            SELECT p.id as product_id, p.name, COALESCE(p.discount_price, p.price) as unit_price,
                   p.stock, p.image_url, c.name as category_name
            FROM products p
            JOIN categories c ON p.category_id = c.id
            WHERE p.id = ?
            '''
            prod = conn.execute(query, (int(pid),)).fetchone()
            if prod:
                subtotal = prod['unit_price'] * qty
                item_dict = dict(prod)
                item_dict['quantity'] = qty
                item_dict['subtotal'] = subtotal
                items.append(item_dict)

    conn.close()
    total_amount = sum(item['subtotal'] for item in items)
    return items, total_amount

def add_to_cart_db(user_id, product_id, quantity=1):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO cart_items (user_id, product_id, quantity)
    VALUES (?, ?, ?)
    ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + excluded.quantity
    ''', (user_id, product_id, quantity))
    conn.commit()
    conn.close()

def update_cart_db(user_id, product_id, quantity):
    conn = get_db_connection()
    if quantity <= 0:
        conn.execute('DELETE FROM cart_items WHERE user_id = ? AND product_id = ?', (user_id, product_id))
    else:
        conn.execute('UPDATE cart_items SET quantity = ? WHERE user_id = ? AND product_id = ?', (quantity, user_id, product_id))
    conn.commit()
    conn.close()

def remove_from_cart_db(user_id, product_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM cart_items WHERE user_id = ? AND product_id = ?', (user_id, product_id))
    conn.commit()
    conn.close()

def clear_cart_db(user_id):
    conn = get_db_connection()
    conn.execute('DELETE FROM cart_items WHERE user_id = ?', (user_id,))
    conn.commit()
    conn.close()

def sync_session_cart_to_db(user_id, session_cart):
    if not session_cart:
        return
    for pid, qty in session_cart.items():
        add_to_cart_db(user_id, int(pid), qty)

# ----------------- ACID Checkout & Order Processing ----------------- #

def process_checkout_transaction(user_id, shipping_info, payment_method, cart_items, total_amount):
    """
    Executes an atomic ACID transaction in SQLite:
    1. Verify sufficient stock for all items
    2. Deduct inventory stock
    3. Insert into orders table
    4. Insert all line items into order_items table
    5. Clear user's cart
    6. Commit transaction (or Rollback on error)
    """
    if not cart_items:
        return None, 'Your cart is empty.'

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        conn.execute('BEGIN TRANSACTION;')

        # Step 1 & 2: Check & Deduct Stock
        for item in cart_items:
            pid = item['product_id']
            qty = item['quantity']
            
            prod_row = cursor.execute('SELECT stock, name FROM products WHERE id = ?', (pid,)).fetchone()
            if not prod_row:
                conn.execute('ROLLBACK;')
                return None, f"Product '{item['name']}' no longer exists."
            
            if prod_row['stock'] < qty:
                conn.execute('ROLLBACK;')
                return None, f"Insufficient stock for '{prod_row['name']}'. Only {prod_row['stock']} available."

            cursor.execute('UPDATE products SET stock = stock - ? WHERE id = ?', (qty, pid))

        # Step 3: Insert Order
        order_number = f"ORD-{datetime.datetime.now().strftime('%Y%m%d')}-{random.randint(1000, 9999)}"
        cursor.execute('''
        INSERT INTO orders (order_number, user_id, total_amount, discount_amount, shipping_fee, final_amount,
                            shipping_name, shipping_email, shipping_phone, shipping_address, payment_method, 
                            payment_status, order_status)
        VALUES (?, ?, ?, 0, 0, ?, ?, ?, ?, ?, ?, 'Completed', 'Processing')
        ''', (order_number, user_id, total_amount, total_amount,
              shipping_info['name'], shipping_info['email'], shipping_info['phone'], shipping_info['address'],
              payment_method))
        
        order_id = cursor.lastrowid

        # Step 4: Insert Order Items
        for item in cart_items:
            cursor.execute('''
            INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity, subtotal)
            VALUES (?, ?, ?, ?, ?, ?)
            ''', (order_id, item['product_id'], item['name'], item['unit_price'], item['quantity'], item['subtotal']))

        # Step 5: Clear Cart
        if user_id:
            cursor.execute('DELETE FROM cart_items WHERE user_id = ?', (user_id,))

        conn.commit()
        return order_id, None

    except Exception as e:
        conn.execute('ROLLBACK;')
        return None, f'Checkout transaction failed: {str(e)}'
    finally:
        conn.close()

# ----------------- Order Inquiries & Status ----------------- #

def get_orders_by_user(user_id):
    conn = get_db_connection()
    orders = conn.execute('SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC', (user_id,)).fetchall()
    result = []
    for o in orders:
        order_dict = dict(o)
        items = conn.execute('''
        SELECT oi.*, p.image_url 
        FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.id
        WHERE oi.order_id = ?
        ''', (o['id'],)).fetchall()
        order_dict['order_items'] = [dict(i) for i in items]
        result.append(order_dict)
    conn.close()
    return result

def get_order_details(order_id):
    conn = get_db_connection()
    order = conn.execute('SELECT * FROM orders WHERE id = ?', (order_id,)).fetchone()
    if not order:
        conn.close()
        return None, []
    
    items = conn.execute('''
    SELECT oi.*, p.image_url
    FROM order_items oi
    LEFT JOIN products p ON oi.product_id = p.id
    WHERE oi.order_id = ?
    ''', (order_id,)).fetchall()
    conn.close()
    return dict(order), [dict(i) for i in items]

def get_all_orders_admin():
    conn = get_db_connection()
    orders = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    result = []
    for o in orders:
        order_dict = dict(o)
        items = conn.execute('SELECT * FROM order_items WHERE order_id = ?', (o['id'],)).fetchall()
        order_dict['order_items'] = [dict(i) for i in items]
        result.append(order_dict)
    conn.close()
    return result

def update_order_status(order_id, status):
    conn = get_db_connection()
    conn.execute('UPDATE orders SET order_status = ? WHERE id = ?', (status, order_id))
    conn.commit()
    conn.close()

# ----------------- Reviews ----------------- #

def get_reviews_for_product(product_id):
    conn = get_db_connection()
    query = '''
    SELECT r.*, u.name as user_name
    FROM reviews r
    JOIN users u ON r.user_id = u.id
    WHERE r.product_id = ?
    ORDER BY r.created_at DESC
    '''
    reviews = conn.execute(query, (product_id,)).fetchall()
    conn.close()
    return reviews

def add_review(product_id, user_id, rating, comment):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO reviews (product_id, user_id, rating, comment)
    VALUES (?, ?, ?, ?)
    ''', (product_id, user_id, rating, comment.strip()))
    
    # Recalculate and update average product rating
    cursor.execute('SELECT AVG(rating) as avg_rating FROM reviews WHERE product_id = ?', (product_id,))
    avg = cursor.fetchone()['avg_rating']
    if avg:
        cursor.execute('UPDATE products SET rating = ? WHERE id = ?', (round(avg, 1), product_id))

    conn.commit()
    conn.close()

# ----------------- Admin Analytics ----------------- #

def get_admin_dashboard_metrics():
    conn = get_db_connection()
    
    total_rev = conn.execute('SELECT COALESCE(SUM(final_amount), 0) as rev FROM orders').fetchone()['rev']
    total_ord = conn.execute('SELECT COUNT(*) as count FROM orders').fetchone()['count']
    total_prod = conn.execute('SELECT COUNT(*) as count FROM products').fetchone()['count']
    total_usr = conn.execute('SELECT COUNT(*) as count FROM users WHERE role = "customer"').fetchone()['count']
    
    recent_orders = conn.execute('SELECT * FROM orders ORDER BY created_at DESC LIMIT 5').fetchall()
    low_stock = conn.execute('SELECT * FROM products WHERE stock <= 15 ORDER BY stock ASC LIMIT 5').fetchall()

    conn.close()
    return {
        'total_revenue': total_rev,
        'total_orders': total_ord,
        'total_products': total_prod,
        'total_users': total_usr,
        'recent_orders': recent_orders,
        'low_stock_products': low_stock
    }
