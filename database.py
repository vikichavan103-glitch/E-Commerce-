import sqlite3
import os
from werkzeug.security import generate_password_hash

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ecommerce.db')

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON;')
    return conn

def init_db(force_recreate=False):
    if force_recreate and os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        print('Existing database removed for fresh setup.')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        role TEXT NOT NULL DEFAULT 'customer',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    ''')

    # 2. Categories Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS categories (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        icon TEXT,
        description TEXT
    );
    ''')

    # 3. Products Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        category_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        slug TEXT UNIQUE NOT NULL,
        description TEXT NOT NULL,
        price REAL NOT NULL CHECK(price > 0),
        discount_price REAL CHECK(discount_price IS NULL OR discount_price < price),
        stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
        image_url TEXT NOT NULL,
        rating REAL DEFAULT 4.5,
        is_featured INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE RESTRICT
    );
    ''')

    # 4. Cart Items Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS cart_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        quantity INTEGER NOT NULL DEFAULT 1 CHECK(quantity > 0),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        UNIQUE(user_id, product_id)
    );
    ''')

    # 5. Orders Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_number TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        total_amount REAL NOT NULL,
        discount_amount REAL DEFAULT 0,
        shipping_fee REAL DEFAULT 0,
        final_amount REAL NOT NULL,
        shipping_name TEXT NOT NULL,
        shipping_email TEXT NOT NULL,
        shipping_phone TEXT NOT NULL,
        shipping_address TEXT NOT NULL,
        payment_method TEXT NOT NULL,
        payment_status TEXT NOT NULL DEFAULT 'Completed',
        order_status TEXT NOT NULL DEFAULT 'Processing',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE RESTRICT
    );
    ''')

    # 6. Order Items Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS order_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        order_id INTEGER NOT NULL,
        product_id INTEGER NOT NULL,
        product_name TEXT NOT NULL,
        unit_price REAL NOT NULL,
        quantity INTEGER NOT NULL,
        subtotal REAL NOT NULL,
        FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE RESTRICT
    );
    ''')

    # 7. Reviews Table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        rating INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
        comment TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );
    ''')

    # 8. Indexes for Optimization
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_order_items_order ON order_items(order_id);')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_reviews_product ON reviews(product_id);')

    conn.commit()

    # Seed data if empty
    cursor.execute('SELECT COUNT(*) as count FROM users')
    if cursor.fetchone()['count'] == 0:
        seed_data(conn)

    conn.close()
    print('Database initialized successfully.')

def seed_data(conn):
    cursor = conn.cursor()
    print('Seeding database with default data...')

    # Seed Users
    admin_pw = generate_password_hash('admin123')
    user_pw = generate_password_hash('john123')
    priya_pw = generate_password_hash('priya123')

    cursor.execute('INSERT INTO users (name, email, password_hash, phone, address, role) VALUES (?, ?, ?, ?, ?, ?)', 
                   ('Admin Master', 'admin@ecommerce.com', admin_pw, '+91 9876543210', '12 Tech Park, Cyber City, Mumbai', 'admin'))
    cursor.execute('INSERT INTO users (name, email, password_hash, phone, address, role) VALUES (?, ?, ?, ?, ?, ?)', 
                   ('John Doe', 'john@example.com', user_pw, '+91 9876543211', '404 Silicon Ave, Tech Zone, Pune', 'customer'))
    cursor.execute('INSERT INTO users (name, email, password_hash, phone, address, role) VALUES (?, ?, ?, ?, ?, ?)', 
                   ('Priya Sharma', 'priya@example.com', priya_pw, '+91 9876543212', '78 Heritage Garden, Bangalore', 'customer'))

    # Seed Categories
    categories = [
        ('Smartphones', 'smartphones', 'bi-phone', 'Latest high-performance smartphones and 5G flagship devices.'),
        ('Laptops & Computers', 'laptops', 'bi-laptop', 'Ultrabooks, gaming rigs, and high-productivity workstations.'),
        ('Audio & Wearables', 'audio-wearables', 'bi-headphones', 'Noise-cancelling headphones, wireless earbuds, and smartwatches.'),
        ('Smart Home & Gadgets', 'smart-home', 'bi-house-gear', 'Smart speakers, lighting, IoT automation, and security cams.'),
        ('Fashion & Lifestyle', 'fashion', 'bi-bag', 'Premium apparel, minimalist watches, and everyday essentials.'),
        ('Cameras & Drones', 'cameras', 'bi-camera', 'DSLRs, mirrorless cameras, 4K aerial drones, and lenses.')
    ]
    cursor.executemany('INSERT INTO categories (name, slug, icon, description) VALUES (?, ?, ?, ?);', categories)

    # Seed Products
    products = [
        # Smartphones (category_id = 1)
        (1, 'UltraPhone 15 Pro Max', 'ultraphone-15-pro-max', 
         'Flagship smartphone featuring Titanium design, 48MP AI triple camera system, A17 Pro bionic chip, 120Hz Super OLED display, and all-day battery life.', 
         129999, 119999, 25, 
         'https://images.unsplash.com/photo-1695048133142-1a20484d2569?auto=format&fit=crop&w=800&q=80', 
         4.9, 1),
        (1, 'Galaxy SuperNova Ultra', 'galaxy-supernova-ultra', 
         'Next-gen AI smartphone with built-in S-Pen, 200MP Quad Zoom camera, Snapdragon 8 Gen 3 processor, Dynamic AMOLED 2X, and satellite connectivity.', 
         124999, 114999, 18, 
         'https://images.unsplash.com/photo-1610945265064-0e34e5519bbf?auto=format&fit=crop&w=800&q=80', 
         4.8, 1),
        (1, 'Pixel Harmony 9 Pro', 'pixel-harmony-9-pro', 
         'Pure Android experience with Google Tensor G4, Gemini AI integrated photo editor, 50MP periscope zoom, and 7 years of OS updates.', 
         89999, 82999, 30, 
         'https://images.unsplash.com/photo-1598327105666-5b89351aff97?auto=format&fit=crop&w=800&q=80', 
         4.7, 0),

        # Laptops (category_id = 2)
        (2, 'MacPro M3 Studio Laptop', 'macpro-m3-studio-laptop', 
         'Blazing-fast M3 Max 16-core CPU, 40-core GPU, 36GB unified memory, 1TB SSD, Liquid Retina XDR screen with 1600 nits peak brightness.', 
         249999, 234999, 12, 
         'https://images.unsplash.com/photo-1517336714731-489689fd1ca8?auto=format&fit=crop&w=800&q=80', 
         4.9, 1),
        (2, 'Zenith Blade 16 Gaming Laptop', 'zenith-blade-16-gaming', 
         'Ultra-thin high-performance gaming laptop with Intel Core i9-14900HX, NVIDIA GeForce RTX 4080 12GB, 32GB DDR5, 240Hz QHD+ Mini-LED display.', 
         199999, 184999, 10, 
         'https://images.unsplash.com/photo-1603302576837-37561b2e2302?auto=format&fit=crop&w=800&q=80', 
         4.8, 1),
        (2, 'AeroBook Carbon 14', 'aerobook-carbon-14', 
         'Featherlight 990g carbon-fiber business laptop, Intel Core Ultra 7 with NPU AI accelerator, 16GB RAM, 512GB SSD, 20-hour battery life.', 
         94999, 87999, 20, 
         'https://images.unsplash.com/photo-1496181133206-80ce9b88a853?auto=format&fit=crop&w=800&q=80', 
         4.6, 0),

        # Audio & Wearables (category_id = 3)
        (3, 'SonicShield Pro Noise Cancelling Headphones', 'sonicshield-pro-headphones', 
         'Industry-leading active noise cancellation with 8 microphones, Hi-Res LDAC audio codecs, 40-hour playback, plush memory foam earcups.', 
         24999, 19999, 45, 
         'https://images.unsplash.com/photo-1505740420928-5e560c06d30e?auto=format&fit=crop&w=800&q=80', 
         4.9, 1),
        (3, 'AirBuds Pulse Wireless Earbuds', 'airbuds-pulse-wireless-earbuds', 
         'True wireless earbuds with spatial audio head tracking, deep bass dual drivers, IPX7 water resistance, transparent sound mode, and wireless charging case.', 
         12999, 9999, 60, 
         'https://images.unsplash.com/photo-1590658268037-6bf12165a8df?auto=format&fit=crop&w=800&q=80', 
         4.7, 0),
        (3, 'Chronos Elite Smartwatch', 'chronos-elite-smartwatch', 
         'Sapphire crystal smartwatch with AMOLED display, ECG monitoring, SpO2 sensor, dual-frequency GPS, 100+ sport modes, 14-day battery.', 
         21999, 17999, 35, 
         'https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=800&q=80', 
         4.8, 1),

        # Smart Home & Gadgets (category_id = 4)
        (4, 'EchoSphere AI Smart Speaker & Hub', 'echosphere-ai-smart-speaker', 
         'Premium 360-degree room-filling acoustic speaker with integrated voice assistant, Zigbee smart home hub, ambient adaptive equalizer.', 
         8999, 6999, 40, 
         'https://images.unsplash.com/photo-1543512214-318c7553f230?auto=format&fit=crop&w=800&q=80', 
         4.6, 0),
        (4, 'Lumina Smart RGB Ambience Lamp', 'lumina-smart-rgb-lamp', 
         '16 million colors smart ambient floor lamp, music sync rhythm mode, voice control compatible with Alexa/Google, sleek modern aluminum bar.', 
         4999, 3799, 50, 
         'https://images.unsplash.com/photo-1507473885765-e6ed057f782c?auto=format&fit=crop&w=800&q=80', 
         4.5, 0),
        (4, 'RoboClean Max Robot Vacuum & Mop', 'roboclean-max-robot-vacuum', 
         'LiDAR navigation robot vacuum with 5000Pa suction power, sonic mopping, auto-empty dustbin station, AI obstacle avoidance camera.', 
         42999, 36999, 15, 
         'https://images.unsplash.com/photo-1518640467707-6811f4a6ab73?auto=format&fit=crop&w=800&q=80', 
         4.7, 1),

        # Fashion & Lifestyle (category_id = 5)
        (5, 'Vintage Leather Explorer Backpack', 'vintage-leather-explorer-backpack', 
         'Handcrafted full-grain Italian leather backpack with padded 15.6 inch laptop sleeve, brass buckle hardware, water-resistant waxed canvas lining.', 
         7999, 5999, 30, 
         'https://images.unsplash.com/photo-1553062407-98eeb64c6a62?auto=format&fit=crop&w=800&q=80', 
         4.8, 0),
        (5, 'AeroFit Performance Running Shoes', 'aerofit-performance-running-shoes', 
         'Engineered mesh upper with responsive nitrogen-infused foam midsole, carbon fiber propulsion plate, and high-traction rubber outsole.', 
         8499, 6499, 40, 
         'https://images.unsplash.com/photo-1542291026-7eec264c27ff?auto=format&fit=crop&w=800&q=80', 
         4.9, 1),
        (5, 'Nomad Minimalist Chronograph Watch', 'nomad-minimalist-chronograph-watch', 
         'Japanese quartz movement, 316L stainless steel case, genuine horween leather strap, 50m water resistance, scratch-resistant sapphire glass.', 
         11999, 8999, 25, 
         'https://images.unsplash.com/photo-1522335789203-aabd1fc54bc9?auto=format&fit=crop&w=800&q=80', 
         4.7, 0),

        # Cameras & Drones (category_id = 6)
        (6, 'SkyMaster 4K Cinematic Drone', 'skymaster-4k-cinematic-drone', 
         'Ultra-compact folding drone with 3-axis gimbal 4K/60fps HDR camera, 10km HD video transmission, omnidirectional obstacle sensors, 38 min flight time.', 
         64999, 58999, 14, 
         'https://images.unsplash.com/photo-1527977966376-1c8408f9f108?auto=format&fit=crop&w=800&q=80', 
         4.9, 1),
        (6, 'Alpha Vision 7 Mirrorless Camera', 'alpha-vision-7-mirrorless-camera', 
         '33MP full-frame Exmor R sensor, BIONZ XR image processor, real-time AI eye autofocus for humans/animals/birds, 4K 60p 10-bit 4:2:2 video.', 
         179999, 164999, 8, 
         'https://images.unsplash.com/photo-1516035069371-29a1b244cc32?auto=format&fit=crop&w=800&q=80', 
         4.9, 1)
    ]

    cursor.executemany('INSERT INTO products (category_id, name, slug, description, price, discount_price, stock, image_url, rating, is_featured) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);', products)

    # Seed Reviews
    reviews = [
        (1, 2, 5, 'Absolutely fantastic phone! The camera clarity and battery life exceeded all my expectations. Super smooth 120Hz display.'),
        (1, 3, 5, 'Premium build and feels featherlight in hand. The AI photo features are genuinely useful.'),
        (4, 2, 5, 'The M3 chip handles heavy video editing and coding seamlessly with zero fan noise. Best laptop ever!'),
        (7, 3, 5, 'The active noise cancellation is pure magic during flights. Bass response is deep and clear.'),
        (14, 2, 5, 'Super comfortable shoes for marathon training! Cushioning is top tier.'),
        (16, 3, 5, 'Amazing drone stability even in windy conditions. 4K footage is razor sharp.')
    ]
    cursor.executemany('INSERT INTO reviews (product_id, user_id, rating, comment) VALUES (?, ?, ?, ?);', reviews)

    # Seed Orders & Order Items
    cursor.execute('INSERT INTO orders (order_number, user_id, total_amount, discount_amount, shipping_fee, final_amount, shipping_name, shipping_email, shipping_phone, shipping_address, payment_method, payment_status, order_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   ('ORD-2026-001', 2, 139998, 10000, 0, 129998, 'John Doe', 'john@example.com', '+91 9876543211', '404 Silicon Ave, Pune', 'UPI', 'Completed', 'Delivered'))
    cursor.execute('INSERT INTO orders (order_number, user_id, total_amount, discount_amount, shipping_fee, final_amount, shipping_name, shipping_email, shipping_phone, shipping_address, payment_method, payment_status, order_status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
                   ('ORD-2026-002', 3, 254998, 15000, 0, 239998, 'Priya Sharma', 'priya@example.com', '+91 9876543212', '78 Heritage Garden, Bangalore', 'Credit Card', 'Completed', 'Processing'))

    cursor.execute('INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity, subtotal) VALUES (?, ?, ?, ?, ?, ?)',
                   (1, 1, 'UltraPhone 15 Pro Max', 119999, 1, 119999))
    cursor.execute('INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity, subtotal) VALUES (?, ?, ?, ?, ?, ?)',
                   (1, 7, 'SonicShield Pro Noise Cancelling Headphones', 19999, 1, 19999))
    cursor.execute('INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity, subtotal) VALUES (?, ?, ?, ?, ?, ?)',
                   (2, 4, 'MacPro M3 Studio Laptop', 234999, 1, 234999))
    cursor.execute('INSERT INTO order_items (order_id, product_id, product_name, unit_price, quantity, subtotal) VALUES (?, ?, ?, ?, ?, ?)',
                   (2, 15, 'Nomad Minimalist Chronograph Watch', 8999, 1, 8999))

    conn.commit()
    print('Seed data inserted successfully.')

if __name__ == '__main__':
    init_db(force_recreate=True)
