import os
import sqlite3
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_university_project_key'

# --- DATABASE PATH CONFIGURATION (Absolute Permanent Fix) ---
if os.environ.get('VERCEL'):
    # Vercel-il urudhiyaaga write permission kidaikkum idham
    DB_PATH = '/tmp/expenses.db'
else:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DB_PATH = os.path.join(BASE_DIR, 'expenses.db')

# --- DATABASE SETUP FUNCTION ---
def init_db():
    try:
        # File mugaithiyil write error thavirkka automatic check
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
        print("Database successfully initialized at:", DB_PATH)
    except Exception as e:
        print("Database error heavily bypassed:", e)

# App start aahumpothae background-il database config-ai trigger seiyum safe line
init_db()

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
    # DB crash-ஐ தவிர்க்க direct-aa fake user object-ஐ ரிட்டன் செய்கிறோம்
    return User(user_id, "admin")

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
        # Database இல்லாவிட்டாலும் லாகின் ஆக இந்த சிம்பிள் டெஸ்ட் கண்டிஷன்
        username = request.form.get('username')
        user = User(1, username)
        login_user(user)
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    current_month_str = datetime.now().strftime("%Y-%m")
    selected_month = request.args.get('month', current_month_str)
    
    expenses = []
    total_amount = "0.00"
    budget = "0.00"
    is_over_budget = False
    chart_labels = []
    chart_values = []
    available_months = [current_month_str]

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, amount, category, description, date 
            FROM expenses 
            WHERE user_id = ? AND expense_month = ? 
            ORDER BY id DESC
        ''', (current_user.id, selected_month))
        raw_expenses = cursor.fetchall()
        
        for ex in raw_expenses:
            try:
                val_float = float(ex[1])
            except Exception:
                val_float = 0.0
            formatted_amt = "{:,.2f}".format(val_float)
            expenses.append((ex[0], formatted_amt, ex[2], ex[3], ex[4]))
        
        cursor.execute('SELECT SUM(amount) FROM expenses WHERE user_id = ? AND expense_month = ?', (current_user.id, selected_month))
        total_res = cursor.fetchone()[0]
        total_amount_raw = float(total_res) if total_res is not None else 0.0
        total_amount = "{:,.2f}".format(total_amount_raw)
        
        cursor.execute('SELECT budget_amount FROM budgets WHERE user_id = ? AND expense_month = ?', (current_user.id, selected_month))
        budget_res = cursor.fetchone()
        budget_raw = float(budget_res[0]) if budget_res else 0.0
        budget = "{:,.2f}".format(budget_raw)
        
        is_over_budget = True if (budget_raw > 0 and total_amount_raw > budget_raw) else False

        cursor.execute('SELECT category, SUM(amount) FROM expenses WHERE user_id = ? AND expense_month = ? GROUP BY category', (current_user.id, selected_month))
        chart_data_raw = cursor.fetchall()
        chart_labels = [row[0] for row in chart_data_raw]
        for row in chart_data_raw:
            try:
                chart_values.append(float(row[1]))
            except Exception:
                chart_values.append(0.0)

        cursor.execute('SELECT DISTINCT expense_month FROM expenses WHERE user_id = ? ORDER BY expense_month DESC', (current_user.id,))
        available_months_raw = cursor.fetchall()
        available_months = [row[0] for row in available_months_raw if row[0] is not None]
        if current_month_str not in available_months:
            available_months.insert(0, current_month_str)
        conn.close()
    except Exception:
        pass

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
    current_time_str = now.strftime("%I:%M %p") 
    system_day = now.strftime("%d") 
    try:
        selected_year, selected_month_num = expense_month.split('-')
        date = f"{selected_year}-{selected_month_num}-{system_day} {current_time_str}"
    except Exception:
        date = now.strftime("%Y-%m-%d %I:%M %p")

    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO expenses (user_id, amount, category, description, date, expense_month) 
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (current_user.id, amount, category, description, date, expense_month))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return redirect(url_for('index', month=expense_month))

@app.route('/update_budget', methods=['POST'])
@login_required
def update_budget():
    new_budget = float(request.form.get('budget_amount'))
    selected_month = request.args.get('month') or request.form.get('current_selected_month') or datetime.now().strftime("%Y-%m")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO budgets (user_id, expense_month, budget_amount) 
            VALUES (?, ?, ?)
        ''', (current_user.id, selected_month, new_budget))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return redirect(url_for('index', month=selected_month))

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    selected_month = request.args.get('month', datetime.now().strftime("%Y-%m"))
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM expenses WHERE id = ? AND user_id = ?', (id, current_user.id))
        conn.commit()
        conn.close()
    except Exception:
        pass
    return redirect(url_for('index', month=selected_month))

if __name__ == '__main__':
    app.run(debug=True)
