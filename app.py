import os
from flask import Flask, render_template, request, redirect, session, flash
from flask_mysqldb import MySQL
import bcrypt
app = Flask(__name__)

print("MYSQL_HOST =", os.getenv("MYSQL_HOST"))
print("MYSQL_USER =", os.getenv("MYSQL_USER"))
print("MYSQL_DB =", os.getenv("MYSQL_DB"))
print("MYSQL_PORT =", os.getenv("MYSQL_PORT"))

app.config['MYSQL_HOST'] = os.getenv('MYSQL_HOST')
app.config['MYSQL_USER'] = os.getenv('MYSQL_USER')
app.config['MYSQL_PASSWORD'] = os.getenv('MYSQL_PASSWORD')
app.config['MYSQL_DB'] = os.getenv('MYSQL_DB')
app.config['MYSQL_PORT'] = int(os.getenv('MYSQL_PORT'))

mysql = MySQL(app)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/user_register', methods=['GET', 'POST'])
def user_register():
    if request.method == 'POST':
        name = request.form['name']
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            return "Passwords do not match"

        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        cur = mysql.connection.cursor()
        cur.execute(
            "INSERT INTO users (name, username, email, password, role) VALUES (%s, %s, %s, %s, %s)",
            (name, username, email, hashed_password, 'student')
        )
        mysql.connection.commit()
        cur.close()

        return redirect('/user_login')

    return render_template('user_register.html')

@app.route('/user_login', methods=['GET', 'POST'])
def user_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cur.fetchone()
        cur.close()

        if user:
            stored_password = user[4]

            if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                session['username'] = user[2]
                session['email'] = user[3]
                return redirect('/user_dashboard')
            else:
                flash("Incorrect password", "password")
                return redirect('/user_login')
        else:
            flash("User not found", "user")
            return redirect('/user_login')
        
    return render_template('user_login.html')

@app.route('/user_dashboard')
def user_dashboard():
    return render_template('user_dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/user_login')

@app.route('/add_complaint', methods=['GET', 'POST'])
def add_complaint():
    if request.method == 'POST':
        name = session['username']
        email = session['email']
        category = request.form['category']
        description = request.form['description']
        # Generate Ticket ID
        cur = mysql.connection.cursor()
        cur.execute("SELECT COUNT(*) FROM complaints")
        count = cur.fetchone()[0] + 1

        ticket_id = f"CMP2026{count:03d}"
        cur = mysql.connection.cursor()
        cur.execute(
            """INSERT INTO complaints (ticket_id, name, email, category, description) VALUES (%s, %s, %s, %s, %s)""",
            (ticket_id, name, email, category, description)
        )
        mysql.connection.commit()
        cur.close()

        return redirect('/complaint_success')

    return render_template('add_complaint.html')

@app.route('/complaint_success')
def complaint_success():
    return render_template('complaint_success.html')

@app.route('/track_complaint')
def track_complaint():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM complaints WHERE email = %s", (session['email'],))
    complaints = cur.fetchall()
    cur.close()

    return render_template('track_complaint.html', complaints=complaints)

@app.route('/view_complaint/<int:complaint_id>')
def view_complaint(complaint_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM complaints WHERE id=%s", (complaint_id,))
    complaint = cur.fetchone()
    cur.close()

    return render_template('view_complaint.html', complaint=complaint)

@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s AND role = 'admin'", (username,))
        admin = cur.fetchone()
        cur.close()

        if admin:
            stored_password = admin[4]

            if isinstance(stored_password, str):
                stored_password = stored_password.encode('utf-8')

            if bcrypt.checkpw(password.encode('utf-8'), stored_password):
                session['admin'] = username
                return redirect('/admin_dashboard')
            else:
                flash("Incorrect password", "password")
                return redirect('/admin_login')

        else:
            flash("Admin not found", "admin")
            return redirect('/admin_login')

    return render_template('admin_login.html')

@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
        return redirect('/admin_login')

    cur = mysql.connection.cursor()

    # All complaints
    search = request.args.get('search')
    status = request.args.get('status')

    query = "SELECT * FROM complaints WHERE 1=1"
    params = []

    if search:
        query += """
        AND (
            ticket_id LIKE %s
            OR name LIKE %s
            OR email LIKE %s
        )
    """
        params.extend([
        f"%{search}%",
        f"%{search}%",
        f"%{search}%"
    ])

    if status:
        query += " AND status = %s"
        params.append(status)

    cur.execute(query, tuple(params))
    complaints = cur.fetchall()
    
    # Counts
    cur.execute("SELECT COUNT(*) FROM complaints")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Pending'")
    pending = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='In Progress'")
    progress = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status='Resolved'")
    resolved = cur.fetchone()[0]

    cur.close()

    return render_template(
        'admin_dashboard.html',
        complaints=complaints,
        total=total,
        pending=pending,
        progress=progress,
        resolved=resolved
    )

@app.route('/update_status', methods=['POST'])
def update_status():
    if 'admin' not in session:
        return redirect('/admin_login')

    complaint_id = request.form['complaint_id']
    new_status = request.form['status']

    cur = mysql.connection.cursor()
    cur.execute(
        "UPDATE complaints SET status=%s WHERE id=%s",
        (new_status, complaint_id)
    )
    mysql.connection.commit()
    cur.close()

    return redirect('/admin_dashboard')

@app.route('/admin_logout')
def admin_logout():
    session.clear()
    return redirect('/admin_login')

if __name__ == "__main__":
    app.run(debug=True)