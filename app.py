import os
import json
from datetime import datetime
from flask import Flask, render_template, render_template_string, request, redirect, url_for, flash, session

app = Flask(__name__)
app.secret_key = 'ss_expense_tracker_fail_safe_key'

USERS_DB = {"1": {"username": "admin"}}
EXPENSES_DB = []
BUDGETS_DB = {}

class MockCurrentUser:
    def __init__(self, id, username):
        self.id = str(id)
        self.username = username
        self.is_authenticated = True

# --- SAFETY TEMPLATE FALLBACK RENDERING ---
def safe_render(template_name, **context):
    try:
        return render_template(template_name, **context)
    except Exception:
        # Template file ungal folder-il illaiyenil crash aagamal intha fallback HTML-ai render seiyum
        if template_name == 'login.html':
            return render_template_string('''
                <!DOCTYPE html>
                <html>
                <head>
                    <title>Login - Expense Tracker</title>
                    <style>
                        body { font-family: Arial, sans-serif; background: #f4f7f6; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
                        .card { background: white; padding: 30px; border-radius: 8px; box-shadow: 0 4px 15px rgba(0,0,0,0.1); width: 100%; max-width: 400px; text-align: center; }
                        input[type="text"] { width: 90%; padding: 10px; margin: 15px 0; border: 1px solid #ccc; border-radius: 4px; }
                        button { background: #28a745; color: white; border: none; padding: 10px 20px; border-radius: 4px; cursor: pointer; width: 95%; font-size: 16px; }
                        h2 { color: #333; }
                    </style>
                </head>
                <body>
                    <div class="card">
                        <h2>SS Expense Tracker</h2>
                        <p>Welcome! Please Login</p>
                        <form method="POST" action="/login">
                            <input type="text" name="username" placeholder="Enter Username (e.g., admin)" required>
                            <button type="submit">Login / Enter</button>
                        </form>
                    </div>
                </body>
                </html>
            ''')
        return f"Template {template_name} configuration missing, but server is running safely!"

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        next_id = str(len(USERS_DB) + 1)
        USERS_DB[next_id] = {"username": username}
        return redirect(url_for('login'))
    return safe_render('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        matched_id = "1"
        for uid, info in USERS_DB.items():
            if info["username"] == username:
                matched_id = uid
                break
        session['user_id'] = matched_id
        session['username'] = username
        return redirect(url_for('index'))
    return safe_render('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    current_user = MockCurrentUser(session['user_id'], session['username'])
    current_month_str = datetime.now().strftime("%Y-%m")
    selected_month = request.args.get('month', current_month_str)
    
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

    return safe_render('index.html', 
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
    expense_month = request.form.get('custom_month') or datetime.now().strftime("%Y-%m")
    
    now = datetime.now()
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
    selected_month = request.form.get('current_selected_month') or datetime.now().strftime("%Y-%m")
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
