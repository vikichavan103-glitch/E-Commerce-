import sys
from database import get_db_connection

# Optional Scikit-Learn & Pandas import with graceful pure-SQLite fallback
try:
    import pandas as pd
    import numpy as np
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    print("[INFO] scikit-learn/pandas not installed. Using pure SQLite recommendation fallback.")

class ProductRecommender:
    def __init__(self):
        self.tfidf_matrix = None
        self.cosine_sim = None
        self.products_df = None
        if ML_AVAILABLE:
            self.vectorizer = TfidfVectorizer(stop_words='english', max_features=5000)
            self.fit()

    def fit(self):
        """Train / refresh TF-IDF model on current catalog in database."""
        if not ML_AVAILABLE:
            return

        try:
            conn = get_db_connection()
            query = '''
            SELECT p.id, p.category_id, p.name, p.slug, p.description, p.price, 
                   p.discount_price, p.stock, p.image_url, p.rating, p.is_featured,
                   c.name as category_name
            FROM products p
            JOIN categories c ON p.category_id = c.id
            '''
            self.products_df = pd.read_sql_query(query, conn)
            conn.close()

            if self.products_df.empty:
                return

            self.products_df['combined_features'] = (
                self.products_df['name'] + ' ' + 
                self.products_df['name'] + ' ' + 
                self.products_df['category_name'] + ' ' + 
                self.products_df['description']
            )

            self.tfidf_matrix = self.vectorizer.fit_transform(self.products_df['combined_features'])
            self.cosine_sim = cosine_similarity(self.tfidf_matrix, self.tfidf_matrix)
        except Exception as e:
            print(f"[WARN] Recommender fit error: {e}")

    def get_similar_products(self, product_id, top_n=4):
        """Content-Based Filtering: Returns products most similar in description & category."""
        if ML_AVAILABLE and self.cosine_sim is not None and self.products_df is not None and not self.products_df.empty:
            try:
                idx_matches = self.products_df.index[self.products_df['id'] == product_id].tolist()
                if idx_matches:
                    idx = idx_matches[0]
                    sim_scores = list(enumerate(self.cosine_sim[idx]))
                    sim_scores = sorted(sim_scores, key=lambda x: x[1], reverse=True)
                    sim_scores = [s for s in sim_scores if s[0] != idx][:top_n]
                    product_indices = [s[0] for s in sim_scores]
                    return self.products_df.iloc[product_indices].to_dict('records')
            except Exception:
                pass

        # Pure SQLite fallback (Same category + highest rated)
        conn = get_db_connection()
        query = '''
        SELECT p.id, p.name, p.price, p.discount_price, p.image_url, p.rating, c.name as category_name
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.category_id = (SELECT category_id FROM products WHERE id = ?)
          AND p.id != ?
        ORDER BY p.rating DESC
        LIMIT ?
        '''
        results = conn.execute(query, (product_id, product_id, top_n)).fetchall()
        conn.close()
        return [dict(r) for r in results]

    def get_frequently_bought_together(self, product_id, top_n=3):
        """Collaborative Filtering: Identifies products frequently ordered in the same cart."""
        conn = get_db_connection()
        query = '''
        SELECT p.id, p.name, p.price, p.discount_price, p.image_url, p.rating, c.name as category_name,
               COUNT(*) as co_occurrence
        FROM order_items oi1
        JOIN order_items oi2 ON oi1.order_id = oi2.order_id AND oi1.product_id != oi2.product_id
        JOIN products p ON oi2.product_id = p.id
        JOIN categories c ON p.category_id = c.id
        WHERE oi1.product_id = ?
        GROUP BY p.id
        ORDER BY co_occurrence DESC, p.rating DESC
        LIMIT ?
        '''
        results = conn.execute(query, (product_id, top_n)).fetchall()
        
        if not results:
            fallback_query = '''
            SELECT p.id, p.name, p.price, p.discount_price, p.image_url, p.rating, c.name as category_name
            FROM products p
            JOIN categories c ON p.category_id = c.id
            WHERE p.category_id = (SELECT category_id FROM products WHERE id = ?)
              AND p.id != ?
            ORDER BY p.rating DESC
            LIMIT ?
            '''
            results = conn.execute(fallback_query, (product_id, product_id, top_n)).fetchall()

        conn.close()
        return [dict(r) for r in results]

    def get_user_recommendations(self, user_id, top_n=4):
        """Hybrid Recommendation: Based on user past orders or top trending picks."""
        conn = get_db_connection()
        if user_id:
            user_products_query = '''
            SELECT DISTINCT product_id FROM order_items oi
            JOIN orders o ON oi.order_id = o.id
            WHERE o.user_id = ?
            UNION
            SELECT DISTINCT product_id FROM cart_items WHERE user_id = ?
            '''
            user_pids = [r['product_id'] for r in conn.execute(user_products_query, (user_id, user_id)).fetchall()]
            if user_pids:
                rec_dict = {}
                for pid in user_pids:
                    similars = self.get_similar_products(pid, top_n=3)
                    for item in similars:
                        if item['id'] not in user_pids:
                            rec_dict[item['id']] = item
                if rec_dict:
                    conn.close()
                    return list(rec_dict.values())[:top_n]

        # Cold start fallback
        default_query = '''
        SELECT p.id, p.name, p.price, p.discount_price, p.image_url, p.rating, p.is_featured,
               c.name as category_name
        FROM products p
        JOIN categories c ON p.category_id = c.id
        WHERE p.is_featured = 1 OR p.rating >= 4.7
        ORDER BY p.rating DESC
        LIMIT ?
        '''
        defaults = conn.execute(default_query, (top_n,)).fetchall()
        conn.close()
        return [dict(d) for d in defaults]

recommender = ProductRecommender()
