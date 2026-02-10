from flask import Flask, render_template, request, redirect, url_for, flash
import mysql.connector
from datetime import date

app = Flask(__name__)
app.secret_key = 'gympro_secret_key'  # REQUIRED for flash messages

# ==========================================
#  DATABASE CONFIGURATION
# ==========================================
db_config = {
    'host': '127.0.0.1',
    'user': 'root',
    'password': 'YOUR_PASSWORD_HERE',  # <--- YOUR PASSWORD
    'database': 'gym_management'
}

# ==========================================
#  SECTION 1: AUTHENTICATION & HOME
# ==========================================

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/signup')
def register_page():
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None 
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        try:
            conn = mysql.connector.connect(**db_config)
            cursor = conn.cursor(dictionary=True)
            
            query = "SELECT * FROM members WHERE email = %s AND password = %s"
            cursor.execute(query, (email, password))
            user = cursor.fetchone()
            
            cursor.close()
            conn.close()

            if user:
                flash(f"Welcome back, {user['full_name']}!", "success")
                return redirect(url_for('dashboard'))
            else:
                error = "❌ Invalid email or password. Please try again."
        except mysql.connector.Error as err:
            error = f"Database Error: {err}"
            
    return render_template('index.html', error=error)

@app.route('/register', methods=['POST'])
def register_member():
    fname = request.form.get('full_name')
    email = request.form.get('email')
    password = request.form.get('password') 
    today_date = date.today()

    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        query = "INSERT INTO members (full_name, email, password, phone_number, join_date, status) VALUES (%s, %s, %s, '000-000-0000', %s, 'active')"
        cursor.execute(query, (fname, email, password, today_date))
        conn.commit()
        flash("Registration successful! Please login.", "success")
        return redirect(url_for('login')) 
    except Exception as e:
        return f"Error: {e}"
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()

# ==========================================
#  SECTION 2: DASHBOARD (Updated with To-Dos)
# ==========================================

@app.route('/dashboard')
def dashboard():
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor(dictionary=True)

        # Stats
        cursor.execute("SELECT SUM(amount) as total FROM billing WHERE status = 'Paid'")
        res = cursor.fetchone()
        revenue = res['total'] if res and res['total'] else 0

        cursor.execute("SELECT COUNT(*) as count FROM members WHERE status = 'active'")
        res = cursor.fetchone()
        active_members = res['count'] if res else 0

        cursor.execute("SELECT COUNT(*) as count FROM trainers")
        res = cursor.fetchone()
        trainers = res['count'] if res else 0

        cursor.execute("SELECT COUNT(*) as count FROM billing WHERE status = 'Pending'")
        res = cursor.fetchone()
        pending = res['count'] if res else 0

        # Popular Classes
        cursor.execute("SELECT class_name, max_capacity FROM classes ORDER BY max_capacity DESC LIMIT 5")
        classes = cursor.fetchall()

        # Overdue Invoices
        cursor.execute("""
            SELECT m.full_name, b.amount, b.due_date 
            FROM billing b JOIN members m ON b.member_id = m.id 
            WHERE b.status = 'Overdue'
        """)
        overdue = cursor.fetchall()

        # NEW: Fetch To-Do List
        cursor.execute("SELECT * FROM todos ORDER BY id DESC")
        todos = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('dashboard.html', 
                               revenue=revenue, 
                               active_members=active_members, 
                               trainers=trainers, 
                               pending=pending, 
                               classes=classes, 
                               overdue=overdue,
                               todos=todos)
    except mysql.connector.Error as err:
        return f"Dashboard Error: {err}"

# --- TO-DO ROUTES ---
@app.route('/todo/add', methods=['POST'])
def add_todo():
    task = request.form.get('task')
    if task:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO todos (task, status) VALUES (%s, 'pending')", (task,))
        conn.commit()
        cursor.close()
        conn.close()
        flash("✅ Task added!", "success")
    return redirect(url_for('dashboard'))

@app.route('/todo/delete/<int:id>')
def delete_todo(id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM todos WHERE id=%s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("🗑️ Task removed.", "success")
    return redirect(url_for('dashboard'))

# ==========================================
#  SECTION 3: MEMBERS (FIXED ADD MEMBER)
# ==========================================

@app.route('/members')
def members_page():
    query = request.args.get('q')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    if query:
        search_term = f"%{query}%"
        cursor.execute("SELECT * FROM members WHERE full_name LIKE %s OR email LIKE %s", (search_term, search_term))
    else:
        cursor.execute("SELECT * FROM members")
    members_data = cursor.fetchall()

    cursor.execute("SELECT member_id FROM attendance WHERE visit_date = CURDATE()")
    checked_in_list = [row['member_id'] for row in cursor.fetchall()]
    
    cursor.close()
    conn.close()
    return render_template('members.html', members=members_data, checked_in=checked_in_list)

@app.route('/members/checkin/<int:id>')
def check_in_member(id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO attendance (member_id, visit_date, visit_time) VALUES (%s, CURDATE(), CURTIME())", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("✅ Member checked in successfully!", "success")
    return redirect(url_for('members_page'))

# --- FIXED ADD MEMBER FUNCTION ---
@app.route('/members/add', methods=['POST'])
def add_member():
    conn = None
    cursor = None
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        # 1. Get Form Data
        name = request.form.get('name')
        email = request.form.get('email')
        status = request.form.get('status')
        join_date = request.form.get('join_date')

        # 2. Check if Email exists BEFORE inserting
        cursor.execute("SELECT id FROM members WHERE email = %s", (email,))
        if cursor.fetchone():
            flash("⚠️ Error: That email is already taken!", "error")
            return redirect(url_for('members_page'))

        # 3. Insert New Member
        query = """INSERT INTO members 
                   (full_name, email, password, status, join_date, phone_number) 
                   VALUES (%s, %s, '12345', %s, %s, '000-000-0000')"""
        
        cursor.execute(query, (name, email, status, join_date))
        conn.commit()
        
        flash("✅ New member added successfully!", "success")
        
    except mysql.connector.Error as err:
        flash(f"❌ Database Error: {err}", "error")
        print(f"Error: {err}") 
    finally:
        # 4. ALWAYS close connection
        if cursor:
            cursor.close()
        if conn and conn.is_connected():
            conn.close()
            
    return redirect(url_for('members_page'))

@app.route('/members/edit', methods=['POST'])
def edit_member():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE members SET full_name=%s, email=%s, status=%s, join_date=%s WHERE id=%s",
                   (request.form.get('name'), request.form.get('email'), request.form.get('status'), request.form.get('join_date'), request.form.get('member_id')))
    conn.commit()
    cursor.close()
    conn.close()
    flash("✏️ Member details updated!", "success")
    return redirect(url_for('members_page'))

@app.route('/members/delete/<int:id>')
def delete_member(id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM attendance WHERE member_id = %s", (id,))
    cursor.execute("DELETE FROM billing WHERE member_id = %s", (id,)) 
    cursor.execute("DELETE FROM members WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("🗑️ Member deleted.", "error")
    return redirect(url_for('members_page'))

# ==========================================
#  SECTION 4: TRAINERS
# ==========================================

@app.route('/trainers')
def trainers_page():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    cursor.execute("SELECT * FROM trainers")
    data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('trainers.html', trainers=data)

@app.route('/trainers/add', methods=['POST'])
def add_trainer():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO trainers (full_name, specialization, email) VALUES (%s, %s, %s)",
                   (request.form.get('fullName'), request.form.get('specialization'), request.form.get('email')))
    conn.commit()
    cursor.close()
    conn.close()
    flash("✅ Trainer added to the team!", "success")
    return redirect(url_for('trainers_page'))

@app.route('/trainers/edit', methods=['POST'])
def edit_trainer():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE trainers SET full_name=%s, specialization=%s, email=%s WHERE id=%s",
                   (request.form.get('fullName'), request.form.get('specialization'), request.form.get('email'), request.form.get('trainerId')))
    conn.commit()
    cursor.close()
    conn.close()
    flash("✏️ Trainer updated successfully!", "success")
    return redirect(url_for('trainers_page'))

@app.route('/trainers/delete/<int:id>')
def delete_trainer(id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM classes WHERE trainer_id = %s", (id,))
    cursor.execute("DELETE FROM trainers WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("🗑️ Trainer removed.", "error")
    return redirect(url_for('trainers_page'))

# ==========================================
#  SECTION 5: CLASSES
# ==========================================

@app.route('/classes')
def classes_page():
    query = request.args.get('q')
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    sql = "SELECT c.*, t.full_name as trainer_name FROM classes c JOIN trainers t ON c.trainer_id = t.id"
    
    if query:
        sql += " WHERE c.class_name LIKE %s OR t.full_name LIKE %s"
        search_term = f"%{query}%"
        cursor.execute(sql + " ORDER BY c.schedule_time ASC", (search_term, search_term))
    else:
        cursor.execute(sql + " ORDER BY c.schedule_time ASC")

    classes_data = cursor.fetchall()
    cursor.execute("SELECT id, full_name FROM trainers")
    trainers_data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('classes.html', classes=classes_data, trainers=trainers_data)

@app.route('/classes/add', methods=['POST'])
def add_class():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO classes (class_name, trainer_id, schedule_day, schedule_time, max_capacity) VALUES (%s, %s, %s, %s, %s)",
                   (request.form.get('className'), request.form.get('trainerId'), request.form.get('scheduleDay'), request.form.get('scheduleTime'), request.form.get('maxCapacity')))
    conn.commit()
    cursor.close()
    conn.close()
    flash("✅ Class scheduled successfully!", "success")
    return redirect(url_for('classes_page'))

@app.route('/classes/edit', methods=['POST'])
def edit_class():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE classes SET class_name=%s, trainer_id=%s, schedule_day=%s, schedule_time=%s, max_capacity=%s WHERE id=%s",
                   (request.form.get('className'), request.form.get('trainerId'), request.form.get('scheduleDay'), request.form.get('scheduleTime'), request.form.get('maxCapacity'), request.form.get('class_id')))
    conn.commit()
    cursor.close()
    conn.close()
    flash("✏️ Class schedule updated!", "success")
    return redirect(url_for('classes_page'))

@app.route('/classes/delete/<int:id>')
def delete_class(id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM classes WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("🗑️ Class cancelled.", "error")
    return redirect(url_for('classes_page'))

# ==========================================
#  SECTION 6: BILLING
# ==========================================

@app.route('/billing')
def billing_page():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    query = "SELECT b.id, m.full_name, b.amount, b.due_date, b.status, b.duration_months FROM billing b JOIN members m ON b.member_id = m.id ORDER BY b.due_date DESC"
    cursor.execute(query)
    billing_data = cursor.fetchall()
    
    cursor.execute("SELECT id, full_name FROM members")
    members_data = cursor.fetchall()
    cursor.close()
    conn.close()
    return render_template('billing.html', billing_records=billing_data, members=members_data)

@app.route('/billing/add', methods=['POST'])
def add_invoice():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO billing (member_id, amount, due_date, status, duration_months) VALUES (%s, %s, %s, %s, %s)",
        (request.form.get('member_id'), request.form.get('amount'), request.form.get('due_date'), request.form.get('status'), request.form.get('duration')))
    conn.commit()
    cursor.close()
    conn.close()
    flash("✅ Invoice created!", "success")
    return redirect(url_for('billing_page'))

@app.route('/billing/pay/<int:id>')
def mark_paid(id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE billing SET status = 'Paid' WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("💰 Payment recorded successfully!", "success")
    return redirect(url_for('billing_page'))

@app.route('/billing/edit', methods=['POST'])
def edit_invoice():
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("UPDATE billing SET amount=%s, status=%s, due_date=%s WHERE id=%s",
                   (request.form.get('amount'), request.form.get('status'), request.form.get('due_date'), request.form.get('invoice_id')))
    conn.commit()
    cursor.close()
    conn.close()
    flash("✏️ Invoice updated!", "success")
    return redirect(url_for('billing_page'))

@app.route('/billing/delete/<int:id>')
def delete_invoice(id):
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM billing WHERE id = %s", (id,))
    conn.commit()
    cursor.close()
    conn.close()
    flash("🗑️ Invoice deleted.", "error")
    return redirect(url_for('billing_page'))

@app.route('/plans')
def plans_page():
    return render_template('plans.html')

if __name__ == '__main__':
    app.run(debug=True)