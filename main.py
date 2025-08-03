from flask import Flask, render_template, request, redirect, session
import sqlite3
import os
import json # Ensure this is imported for potential JSON handling of 'items'

app = Flask(__name__)
app.secret_key = 'your_secret_key' # IMPORTANT: In production, use a strong, randomly generated key!

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect('merchant.db')
    cur = conn.cursor()

    # Merchants
    cur.execute('''
        CREATE TABLE IF NOT EXISTS merchants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            shop_name TEXT NOT NULL
        )
    ''')

    # Users
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Orders
    cur.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            shop_name TEXT,
            user TEXT,
            items TEXT, -- Storing items as a JSON string
            status TEXT DEFAULT 'pending'
        )
    ''')

    conn.commit()
    conn.close()

init_db()

# --- Routes ---
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/merchant')
def merchant_home():
    return render_template('merchant.html')

@app.route('/register', methods=['GET', 'POST'])
def merchant_register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        shop_name = request.form['shop_name']

        conn = sqlite3.connect('merchant.db')
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO merchants (username, password, shop_name) VALUES (?, ?, ?)",
                        (username, password, shop_name))
            conn.commit()
            return redirect('/login')
        except sqlite3.IntegrityError:
            return "Username already taken"
        finally:
            conn.close()

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def merchant_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('merchant.db')
        cur = conn.cursor()
        cur.execute("SELECT shop_name FROM merchants WHERE username=? AND password=?", (username, password))
        result = cur.fetchone()
        conn.close()

        if result:
            session['merchant'] = username
            session['shop_name'] = result[0]
            return redirect('/dashboard')
        else:
            return "Invalid credentials"

    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'merchant' not in session:
        return redirect('/login')

    shop_name = session['shop_name']
    conn = sqlite3.connect('merchant.db')
    cur = conn.cursor()
    # Fetch all orders for this merchant's shop, excluding 'completed' and 'deleted'
    cur.execute("SELECT id, user, items, status FROM orders WHERE shop_name=? AND status NOT IN ('completed', 'deleted')", (shop_name,))
    raw_orders = cur.fetchall()
    conn.close()

    orders_for_template = []
    for order_id, user, items_str, status in raw_orders:
        try:
            # Attempt to parse items string as JSON
            items_list = json.loads(items_str)
        except (json.JSONDecodeError, TypeError):
            # Fallback if items_str is not valid JSON (e.g., plain text)
            items_list = items_str # Keep it as a string
        orders_for_template.append({
            'id': order_id,
            'user': user,
            'items': items_list,
            'status': status
        })

    # No longer fetching just distinct customers, but full orders
    return render_template('dashboard.html', username=session['merchant'], shop_name=shop_name, orders=orders_for_template)

@app.route('/merchant/orders/<user>')
def view_customer_orders(user):
    # This route might become less necessary if dashboard shows all relevant orders.
    # However, keeping it for now if there's a specific need to view a single customer's orders.
    if 'merchant' not in session:
        return redirect('/login')

    shop_name = session['shop_name']
    conn = sqlite3.connect('merchant.db')
    cur = conn.cursor()
    # Fetch orders for a specific user within this merchant's shop
    cur.execute("SELECT id, items, status FROM orders WHERE shop_name=? AND user=? AND status NOT IN ('completed', 'deleted')", (shop_name, user))
    raw_orders = cur.fetchall()
    conn.close()

    orders_for_template = []
    for order_id, items_str, status in raw_orders:
        try:
            items_list = json.loads(items_str)
        except (json.JSONDecodeError, TypeError):
            items_list = items_str
        orders_for_template.append({
            'id': order_id,
            'items': items_list,
            'status': status
        })

    return render_template('merchant_orders.html', customer=user, orders=orders_for_template)

@app.route('/mark/<int:order_id>/<status>')
def mark_order_status(order_id, status):
    if 'merchant' not in session:
        return redirect('/login') # Only logged-in merchants can mark orders

    conn = sqlite3.connect('merchant.db')
    cur = conn.cursor()
    cur.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
    conn.commit()
    conn.close()
    return redirect('/dashboard') # Redirect back to the dashboard after marking

@app.route('/delete_order/<int:order_id>')
def delete_order(order_id):
    if 'merchant' not in session:
        return redirect('/login') # Only logged-in merchants can delete orders

    conn = sqlite3.connect('merchant.db')
    cur = conn.cursor()
    # For a soft delete, update status to 'deleted'. Hard delete would be DELETE FROM.
    cur.execute("UPDATE orders SET status='deleted' WHERE id=?", (order_id,))
    conn.commit()
    conn.close()
    return redirect('/dashboard') # Redirect back to the dashboard

@app.route('/user_register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('merchant.db')
        cur = conn.cursor()
        try:
            cur.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, password))
            conn.commit()
            return redirect('/user_login')
        except sqlite3.IntegrityError:
            return "Username already taken"
        finally:
            conn.close()

    return render_template('user_register.html')

@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('merchant.db')
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        result = cur.fetchone()
        conn.close()

        if result:
            session['user'] = username
            return redirect('/user_dashboard')
        else:
            return "Invalid credentials"

    return render_template('user_login.html')

@app.route('/user_dashboard')
def user_dashboard():
    if 'user' in session:
        conn = sqlite3.connect('merchant.db')
        cur = conn.cursor()
        cur.execute("SELECT shop_name FROM merchants")
        shops = [row[0] for row in cur.fetchall()]
        conn.close()
        return render_template('user_dashboard.html', shops=shops)
    return redirect('/user_login')

@app.route('/user')
def user():
    return render_template('user_select.html')

@app.route('/buy/<shop_name>', methods=['GET', 'POST'])
def buy(shop_name):
    if 'user' not in session:
        return redirect('/user_login')

    if request.method == 'POST':
        items_data = request.form['items_data'] # This should ideally be a JSON string from frontend
        conn = sqlite3.connect('merchant.db')
        cur = conn.cursor()
        # Store items as a JSON string to preserve structure
        cur.execute("INSERT INTO orders (shop_name, user, items) VALUES (?, ?, ?)",
                    (shop_name, session['user'], items_data))
        conn.commit()
        conn.close()
        return redirect('/user_orders')

    return render_template('user_buy.html', shop_name=shop_name)

@app.route('/user_orders')
def user_orders():
    if 'user' not in session:
        return redirect('/user_login')

    conn = sqlite3.connect('merchant.db')
    cur = conn.cursor()
    # Fetch all orders for the logged-in user, excluding 'deleted'
    cur.execute("SELECT shop_name, items, status FROM orders WHERE user=? AND status != 'deleted'", (session['user'],))
    raw_orders = cur.fetchall()
    conn.close()

    orders_for_template = []
    for shop_name, items_str, status in raw_orders:
        try:
            # Attempt to parse items string as JSON
            # This expects items_str to be like '[{"name": "ItemA", "qty": 2}]'
            parsed_items = json.loads(items_str)
        except (json.JSONDecodeError, TypeError):
            # Fallback if items_str is not valid JSON
            parsed_items = items_str # Keep it as a string if parsing fails
        orders_for_template.append({
            'shop_name': shop_name,
            'items': parsed_items, # Pass parsed list or original string
            'status': status
        })

    return render_template('user_orders.html', orders=orders_for_template)


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)