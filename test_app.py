import unittest
import os
from app import app
from database import init_db, get_db_connection
import models
from recommender import recommender

class ECommerceTestCase(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    def test_database_and_seed_data(self):
        conn = get_db_connection()
        products_count = conn.execute('SELECT COUNT(*) as c FROM products').fetchone()['c']
        categories_count = conn.execute('SELECT COUNT(*) as c FROM categories').fetchone()['c']
        users_count = conn.execute('SELECT COUNT(*) as c FROM users').fetchone()['c']
        orders_count = conn.execute('SELECT COUNT(*) as c FROM orders').fetchone()['c']
        conn.close()

        self.assertGreaterEqual(products_count, 15, "Products should have at least 15 seeded items")
        self.assertGreaterEqual(categories_count, 6, "Categories should have 6 seeded categories")
        self.assertGreaterEqual(users_count, 3, "Users should have admin and customer accounts")
        self.assertGreaterEqual(orders_count, 2, "Orders should have seeded co-purchases")
        print("[PASS] Database and Seed Data validation passed.")

    def test_recommender_content_and_collaborative(self):
        similar = recommender.get_similar_products(product_id=1, top_n=3)
        self.assertIsInstance(similar, list)
        self.assertGreater(len(similar), 0)
        
        fbt = recommender.get_frequently_bought_together(product_id=1, top_n=2)
        self.assertIsInstance(fbt, list)
        self.assertGreater(len(fbt), 0)
        print("[PASS] AI/ML Recommendation Engine validation passed.")

    def test_http_routes(self):
        res = self.client.get('/')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'NovaMart', res.data)

        res = self.client.get('/products')
        self.assertEqual(res.status_code, 200)

        res = self.client.get('/products?q=Laptop')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'MacPro', res.data)

        res = self.client.get('/product/1')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'UltraPhone', res.data)

        res = self.client.get('/cart')
        self.assertEqual(res.status_code, 200)

        res = self.client.get('/login')
        self.assertEqual(res.status_code, 200)
        print("[PASS] Core HTTP Routes & Catalog rendering passed.")

    def test_cart_and_acid_checkout(self):
        user_id = 2
        models.add_to_cart_db(user_id, product_id=3, quantity=2)
        
        items, total = models.get_cart_items_for_user(user_id=user_id)
        self.assertGreaterEqual(len(items), 1)

        conn = get_db_connection()
        initial_stock = conn.execute('SELECT stock FROM products WHERE id = 3').fetchone()['stock']
        conn.close()

        shipping_info = {
            'name': 'John Doe',
            'email': 'john@example.com',
            'phone': '+91 9876543211',
            'address': '404 Silicon Ave, Tech Zone, Pune'
        }
        order_id, err = models.process_checkout_transaction(user_id, shipping_info, 'UPI', items, total)
        self.assertIsNone(err)
        self.assertIsNotNone(order_id)

        conn = get_db_connection()
        new_stock = conn.execute('SELECT stock FROM products WHERE id = 3').fetchone()['stock']
        conn.close()
        self.assertEqual(new_stock, initial_stock - 2)

        items_after, _ = models.get_cart_items_for_user(user_id=user_id)
        self.assertEqual(len(items_after), 0)
        print("[PASS] Cart and ACID Checkout Transaction passed.")

    def test_authentication_and_admin_security(self):
        res = self.client.post('/login', data={'email': 'john@example.com', 'password': 'john123'}, follow_redirects=True)
        self.assertEqual(res.status_code, 200)

        res = self.client.get('/my_orders')
        self.assertEqual(res.status_code, 200)

        self.client.get('/logout')

        res = self.client.get('/admin', follow_redirects=True)
        self.assertIn(b'Access denied', res.data)

        self.client.post('/login', data={'email': 'admin@ecommerce.com', 'password': 'admin123'}, follow_redirects=True)
        res = self.client.get('/admin')
        self.assertEqual(res.status_code, 200)
        self.assertIn(b'Administrator Portal', res.data)
        print("[PASS] Authentication & Role-Based Access Control passed.")

if __name__ == '__main__':
    unittest.main()
