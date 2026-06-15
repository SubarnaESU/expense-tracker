import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'your_university_project_key'

# --- DATABASE PATH CONFIGURATION ---
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# --- DATABASE PATH CONFIGURATION ---
if os.environ.get('VERCEL'):
    # Vercel cloud-il run aagum pothu temporary path எடுக்கும்
    DB_PATH = '/tmp/expenses.db'
else:
    # Ungaloda local computer-il run aagum pothu sariyaana local path எடுக்கும்
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DB_PATH = os.path.join(BASE_DIR, 'expenses.db')
# --- LOGIN MANAGER SETUP ---
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('SELECT id, username FROM users WHERE id = ?', (user_id,))
    user_data = cursor.fetchone()
    conn.close()
    if user_data:
        return User(user_data[0], user_data[1])
    return None

# --- DATABASE SETUP ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT UNIQUE, password TEXT)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            user_id INTEGER, 
            amount REAL, 
            category TEXT, 
            description TEXT, 
            date TEXT,
            expense_month TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS budgets (
            user_id INTEGER, 
            expense_month TEXT,
            budget_amount REAL,
            PRIMARY KEY (user_id, expense_month)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- ROUTES ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = generate_password_hash(request.form.get('password'))
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, password))
            conn.commit()
            conn.close()
            flash('Registration successful! Please login.')
            return redirect(url_for('login'))
        except Exception:
            flash('Username already exists!')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT id, username, password FROM users WHERE username = ?', (username,))
        user_data = cursor.fetchone()
        conn.close()
        if user_data and check_password_hash(user_data[2], password):
            user = User(user_data[0], user_data[1])
            login_user(user)
            return redirect(url_for('index'))
        flash('Invalid credentials!')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

# MAIN DASHBOARD ROUTE
@app.route('/')
@login_required
def index():
    current_month_str = datetime.now().strftime("%Y-%m")
    selected_month = request.args.get('month', current_month_str)
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. Fetch Selected Month Expenses only
    cursor.execute('''
        SELECT id, amount, category, description, date 
        FROM expenses 
        WHERE user_id = ? AND expense_month = ? 
        ORDER BY id DESC
    ''', (current_user.id, selected_month))
    raw_expenses = cursor.fetchall()
    
    expenses = []
    for ex in raw_expenses:
        try:
            val_float = float(ex[1])
        except Exception:
            val_float = 0.0
            
        formatted_amt = "{:,.2f}".format(val_float)
        expenses.append((ex[0], formatted_amt, ex[2], ex[3], ex[4]))
    
    # 2. Total Calculation for Selected Month
    cursor.execute('SELECT SUM(amount) FROM expenses WHERE user_id = ? AND expense_month = ?', (current_user.id, selected_month))
    total_res = cursor.fetchone()[0]
    
    try:
        total_amount_raw = float(total_res) if total_res is not None else 0.0
    except Exception:
        total_amount_raw = 0.0
        
    total_amount = "{:,.2f}".format(total_amount_raw)
    
    # 3. Fetch User Budget for the Specific Selected Month (0.00 if empty)
    cursor.execute('SELECT budget_amount FROM budgets WHERE user_id = ? AND expense_month = ?', (current_user.id, selected_month))
    budget_res = cursor.fetchone()
    
    try:
        budget_raw = float(budget_res[0]) if budget_res else 0.0
    except Exception:
        budget_raw = 0.0
        
    budget = "{:,.2f}".format(budget_raw)
    
    # 4. Budget Alert Evaluation
    is_over_budget = True if (budget_raw > 0 and total_amount_raw > budget_raw) else False

    # 5. Chart Data Fetching for Selected Month
    cursor.execute('SELECT category, SUM(amount) FROM expenses WHERE user_id = ? AND expense_month = ? GROUP BY category', (current_user.id, selected_month))
    chart_data_raw = cursor.fetchall()
    chart_labels = [row[0] for row in chart_data_raw]
    chart_values = []
    for row in chart_data_raw:
        try:
            chart_values.append(float(row[1]))
        except Exception:
            chart_values.append(0.0)

    # 6. Get Available Months List for Dropdown
    cursor.execute('SELECT DISTINCT expense_month FROM expenses WHERE user_id = ? ORDER BY expense_month DESC', (current_user.id,))
    available_months_raw = cursor.fetchall()
    available_months = [row[0] for row in available_months_raw if row[0] is not None]
    
    if current_month_str not in available_months:
        available_months.insert(0, current_month_str)

    conn.close()
    return render_template('index.html', 
                           expenses=expenses, 
                           total_amount=total_amount, 
                           budget=budget, 
                           is_over_budget=is_over_budget,
                           chart_labels=json.dumps(chart_labels), 
                           chart_values=json.dumps(chart_values),
                           available_months=available_months,
                           selected_month=selected_month)

@app.route('/add', methods=['POST'])
@login_required
def add():
    amount = float(request.form.get('amount'))
    category = request.form.get('category')
    description = request.form.get('description')
    
    expense_month = request.form.get('custom_month') 
    
    now = datetime.now()
    # [மாற்றம் செய்யப்பட்ட இடம்]: 24 மணிநேரத்திற்குப் பதிலாக AM/PM வடிவம் (%I:%M %p)
    current_time_str = now.strftime("%I:%M %p") 
    system_day = now.strftime("%d") 
    
    try:
        selected_year, selected_month_num = expense_month.split('-')
        date = f"{selected_year}-{selected_month_num}-{system_day} {current_time_str}"
    except Exception:
        date = now.strftime("%Y-%m-%d %I:%M %p")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO expenses (user_id, amount, category, description, date, expense_month) 
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (current_user.id, amount, category, description, date, expense_month))
    conn.commit()
    conn.close()
    return redirect(url_for('index', month=expense_month))

@app.route('/update_budget', methods=['POST'])
@login_required
def update_budget():
    new_budget = float(request.form.get('budget_amount'))
    selected_month = request.args.get('month') or request.form.get('current_selected_month') or datetime.now().strftime("%Y-%m")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO budgets (user_id, expense_month, budget_amount) 
        VALUES (?, ?, ?)
    ''', (current_user.id, selected_month, new_budget))
    conn.commit()
    conn.close()
    return redirect(url_for('index', month=selected_month))

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    selected_month = request.args.get('month', datetime.now().strftime("%Y-%m"))
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM expenses WHERE id = ? AND user_id = ?', (id, current_user.id))
    conn.commit()
    conn.close()
    return redirect(url_for('index', month=selected_month))

if __name__ == '__main__':
    app.run(debug=True)
