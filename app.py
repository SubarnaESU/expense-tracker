import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user

app = Flask(__name__, template_folder='templates')
app.secret_key = 'your_university_project_key'

# --- DATA STORAGE BYPASS (No SQLite Permission Blocks) ---
# Cloud write crashes-ai thavirka database illamal python list memory use seigirom
USERS_DB = {"1": {"username": "admin"}}
EXPENSES_DB = []
BUDGETS_DB = {}

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
    if str(user_id) in USERS_DB:
        return User(user_id, USERS_DB[str(user_id)]["username"])
    return User(user_id, "User")

# Dummy database init definition to avoid missing references
def init_db():
    pass

# --- ROUTES ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        next_id = str(len(USERS_DB) + 1)
        USERS_DB[next_id] = {"username": username}
        flash('Registration successful! Please login.')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        # Database crash thavirka ippo entha text username koduthalum direct login aahum
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
    
    # Filter memory expenses for the user and month
    filtered_expenses = [ex for ex in EXPENSES_DB if ex['user_id'] == current_user.id and ex['expense_month'] == selected_month]
    
    expenses = []
    total_amount_raw = 0.0
    for ex in filtered_expenses:
        try:
            amt = float(ex['amount'])
        except Exception:
            amt = 0.0
        total_amount_raw += amt
        expenses.append((ex['id'], "{:,.2f}".format(amt), ex['category'], ex['description'], ex['date']))
    
    total_amount = "{:,.2f}".format(total_amount_raw)
    
    budget_key = f"{current_user.id}_{selected_month}"
    budget_raw = float(BUDGETS_DB.get(budget_key, 0.0))
    budget = "{:,.2f}".format(budget_raw)
    
    is_over_budget = True if (budget_raw > 0 and total_amount_raw > budget_raw) else False

    # Categories chart setup
    cat_totals = {}
    for ex in filtered_expenses:
        cat = ex['category']
        try:
            amt = float(ex['amount'])
        except Exception:
            amt = 0.0
        cat_totals[cat] = cat_totals.get(cat, 0.0) + amt
        
    chart_labels = list(cat_totals.keys())
    chart_values = list(cat_totals.values())

    # Available months timeline collection
    user_months = set([ex['expense_month'] for ex in EXPENSES_DB if ex['user_id'] == current_user.id])
    user_months.add(current_month_str)
    available_months = sorted(list(user_months), reverse=True)

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
    amount = request.form.get('amount')
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

    EXPENSES_DB.append({
        "id": len(EXPENSES_DB) + 1,
        "user_id": current_user.id,
        "amount": amount,
        "category": category,
        "description": description,
        "date": date,
        "expense_month": expense_month
    })
    return redirect(url_for('index', month=expense_month))

@app.route('/update_budget', methods=['POST'])
@login_required
def update_budget():
    new_budget = request.form.get('budget_amount')
    selected_month = request.args.get('month') or request.form.get('current_selected_month') or datetime.now().strftime("%Y-%m")
    
    budget_key = f"{current_user.id}_{selected_month}"
    BUDGETS_DB[budget_key] = new_budget
    return redirect(url_for('index', month=selected_month))

@app.route('/delete/<int:id>')
@login_required
def delete(id):
    global EXPENSES_DB
    selected_month = request.args.get('month', datetime.now().strftime("%Y-%m"))
    EXPENSES_DB = [ex for ex in EXPENSES_DB if not (ex['id'] == id and ex['user_id'] == current_user.id)]
    return redirect(url_for('index', month=selected_month))

if __name__ == '__main__':
    app.run(debug=True)
