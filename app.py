import os
import json
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, flash, session

app = Flask(__name__, template_folder='templates')
app.secret_key = 'ss_expense_tracker_secure_super_key'

# --- DATA STORAGE BYPASS (Mutrilumaaga framework crash thavirkkum in-memory array) ---
USERS_DB = {"1": {"username": "admin"}}
EXPENSES_DB = []
BUDGETS_DB = {}

# Mock User object setup to keep index.html variables perfectly functional
class MockCurrentUser:
    def __init__(self, id, username):
        self.id = str(id)
        self.username = username
        self.is_authenticated = True

# --- ROUTES ---

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        next_id = str(len(USERS_DB) + 1)
        USERS_DB[next_id] = {"username": username}
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        
        # Checking profile allocation pipeline
        matched_id = "1"
        for uid, info in USERS_DB.items():
            if info["username"] == username:
                matched_id = uid
                break
        
        # Native flask session optimization management        
        session['user_id'] = matched_id
        session['username'] = username
        return redirect(url_for('index'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    # User session validate filter security rule
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = MockCurrentUser(session['user_id'], session['username'])
    
    current_month_str = datetime.now().strftime("%Y-%m")
    selected_month = request.args.get('month', current_month_str)
    
    # Filter memory logic parsing arrays safely
    filtered_expenses = [ex for ex in EXPENSES_DB if str(ex['user_id']) == str(current_user.id) and ex['expense_month'] == selected_month]
    
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
    try:
        budget_raw = float(BUDGETS_DB.get(budget_key, 0.0))
    except Exception:
        budget_raw = 0.0
    budget = "{:,.2f}".format(budget_raw)
    
    is_over_budget = True if (budget_raw > 0 and total_amount_raw > budget_raw) else False

    # Charts execution values mapping configuration
    cat_totals = {}
    for ex in filtered_expenses:
        cat = ex['category'] if ex['category'] else 'General'
        try:
            amt = float(ex['amount'])
        except Exception:
            amt = 0.0
        cat_totals[cat] = cat_totals.get(cat, 0.0) + amt
        
    chart_labels = list(cat_totals.keys())
    chart_values = list(cat_totals.values())

    user_months = set([ex['expense_month'] for ex in EXPENSES_DB if str(ex['user_id']) == str(current_user.id)])
    user_months.add(current_month_str)
    available_months = sorted(list(user_months), reverse=True)

    return render_template('index.html', 
                           current_user=current_user,
                           expenses=expenses, 
                           total_amount=total_amount, 
                           budget=budget, 
                           is_over_budget=is_over_budget,
                           chart_labels=json.dumps(chart_labels), 
                           chart_values=json.dumps(chart_values),
                           available_months=available_months,
                           selected_month=selected_month)

@app.route('/add', methods=['POST'])
def add():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = MockCurrentUser(session['user_id'], session['username'])
    amount = request.form.get('amount')
    category = request.form.get('category')
    description = request.form.get('description')
    expense_month = request.form.get('custom_month') 
    
    if not expense_month:
        expense_month = datetime.now().strftime("%Y-%m")
        
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
        "user_id": str(current_user.id),
        "amount": amount if amount else "0",
        "category": category if category else "General",
        "description": description if description else "",
        "date": date,
        "expense_month": expense_month
    })
    return redirect(url_for('index', month=expense_month))

@app.route('/update_budget', methods=['POST'])
def update_budget():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = MockCurrentUser(session['user_id'], session['username'])
    new_budget = request.form.get('budget_amount')
    selected_month = request.args.get('month') or request.form.get('current_selected_month') or datetime.now().strftime("%Y-%m")
    
    budget_key = f"{current_user.id}_{selected_month}"
    BUDGETS_DB[budget_key] = new_budget if new_budget else "0"
    return redirect(url_for('index', month=selected_month))

@app.route('/delete/<int:id>')
def delete(id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = MockCurrentUser(session['user_id'], session['username'])
    global EXPENSES_DB
    selected_month = request.args.get('month', datetime.now().strftime("%Y-%m"))
    EXPENSES_DB = [ex for ex in EXPENSES_DB if not (ex['id'] == id and str(ex['user_id']) == str(current_user.id))]
    return redirect(url_for('index', month=selected_month))

app.debug = False
