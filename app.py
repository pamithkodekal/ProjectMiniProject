from flask import Flask, render_template, request, redirect, url_for, flash, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import os
from flask_mail import Mail, Message
from datetime import datetime

# ==========================
# APP CONFIGURATION
# ==========================
app = Flask(__name__)
app.secret_key = "supersecretkey"

# ==========================
# EMAIL CONFIGURATION (Placeholders - Email Functionality is Disabled)
# ==========================
# Note: These placeholders remain to avoid configuration errors, but the
# send_notification_email function below is set to return False immediately.
app.config["MAIL_SERVER"] = "smtp.gmail.com"
app.config["MAIL_PORT"] = 587
app.config["MAIL_USE_TLS"] = True
app.config["MAIL_USERNAME"] = "YOUR_GMAIL_ADDRESS" 
app.config["MAIL_PASSWORD"] = "YOUR_GMAIL_APP_PASSWORD" 
app.config["MAIL_DEFAULT_SENDER"] = "YOUR_GMAIL_ADDRESS" 

mail = Mail(app) # Initialize Flask-Mail

# Path to database
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(BASE_DIR, "instance", "students.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)

# ==========================
# DATABASE MODELS
# ==========================
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(50), default='teacher') 
    email = db.Column(db.String(100), unique=True, nullable=True)


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    roll_no = db.Column(db.Integer, nullable=False, unique=True)
    name = db.Column(db.String(100), nullable=False)
    standard = db.Column(db.String(50), nullable=False)
    attendance = db.Column(db.String(50))
    health_issues = db.Column(db.String(200))
    assignments_pending = db.Column(db.String(200))
    assignments_submitted = db.Column(db.String(200))
    remarks = db.Column(db.String(200))
    parent_email = db.Column(db.String(100))
    
    # Relationship: Student (roll_no) -> Complaints (student_roll_no)
    complaints = db.relationship('Complaint', backref='student_ref', lazy='dynamic', 
                                 primaryjoin='Student.roll_no == Complaint.student_roll_no')


class Complaint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_roll_no = db.Column(db.Integer, db.ForeignKey('student.roll_no'), nullable=False)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.String(500), nullable=False)
    teacher_username = db.Column(db.String(100), nullable=False)
    date_filed = db.Column(db.DateTime, default=db.func.current_timestamp())
    status = db.Column(db.String(50), default='Pending') 

# ==========================
# EMAIL SENDER HELPER FUNCTION (Disabled)
# ==========================
def send_notification_email(parent_email, student_name, event_type, details=""):
    """Sends a generic notification email."""
    
    # --- TEMPORARILY DISABLED EMAIL LOGIC ---
    # Since email configuration is not set up, we skip the connection attempt
    # to prevent warnings and errors in the console.
    print(f"INFO: Email notification feature skipped for {student_name} ({event_type}).")
    return False

# ==========================
# DATABASE INITIALIZATION
# ==========================
with app.app_context():
    db.create_all()
    print("✅ Database ready (students.db)")

# ==========================
# ROUTES
# ==========================

@app.route("/")
def home():
    if "user_id" in session and session.get("role") == "teacher":
        return redirect(url_for("view_students"))
    if "parent_lookup_id" in session and session.get("role") == "parent":
        return redirect(url_for("parent_dashboard"))
        
    return render_template("login.html")

# ---------- TEACHER REGISTRATION ----------
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        role = request.form.get("role", "teacher") 

        if User.query.filter_by(username=username).first():
            flash("Username already exists!", "danger")
            return redirect(url_for("register"))

        hashed_pw = generate_password_hash(password)
        new_user = User(username=username, email=email, password=hashed_pw, role=role) 
        db.session.add(new_user)
        db.session.commit()

        flash("Registration successful! Please log in.", "success")
        return redirect(url_for("home"))

    return render_template("register.html")

# ---------- PARENT LOOKUP/LOGIN ----------
@app.route("/parent-lookup", methods=["POST"])
def parent_lookup():
    roll_no = request.form.get("roll_no")
    parent_email = request.form.get("parent_email")

    if not roll_no or not parent_email:
        flash("Please provide both Enrollment Number and Parent Email.", "danger")
        return redirect(url_for("home"))
        
    try:
        roll_no = int(roll_no)
    except ValueError:
        flash("Invalid Enrollment Number format.", "danger")
        return redirect(url_for("home"))

    student = Student.query.filter_by(roll_no=roll_no, parent_email=parent_email).first()

    if student:
        session["parent_lookup_id"] = student.id
        session["parent_lookup_roll_no"] = student.roll_no
        session["role"] = "parent"
        flash(f"Welcome to the dashboard for {student.name}!", "success")
        return redirect(url_for("parent_dashboard"))
    else:
        flash("Invalid Enrollment Number or Email. Please check your details.", "danger")
        return redirect(url_for("home"))

@app.route("/login", methods=["POST"])
def login():
    username = request.form.get("username")
    password = request.form.get("password")

    user = User.query.filter_by(username=username).first()
    if user and check_password_hash(user.password, password):
        session["user_id"] = user.id
        session["role"] = user.role
        flash("Teacher Login successful!", "success")
        return redirect(url_for("view_students"))
    else:
        # Fallback to parent lookup if standard login fails and parent fields are present
        if request.form.get("roll_no") and request.form.get("parent_email"):
            return parent_lookup() 
        
        flash("Invalid teacher credentials!", "danger")
        return redirect(url_for("home"))
    

@app.route("/logout")
def logout():
    session.pop("user_id", None)
    session.pop("role", None)
    session.pop("parent_lookup_id", None)
    session.pop("parent_lookup_roll_no", None)
    flash("Logged out successfully!", "info")
    return redirect(url_for("home"))

# ---------- DASHBOARD & STUDENT MANAGEMENT (Teacher) ----------

@app.route("/teacher-dashboard") 
def view_students():
    if "user_id" not in session or session.get("role") != "teacher":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("home"))

    students = Student.query.all()
    return render_template("teacher_dashboard.html", students=students)


@app.route("/add-student", methods=["GET", "POST"])
def add_student():
    if "user_id" not in session or session.get("role") != "teacher":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("home"))

    if request.method == "POST":
        try:
            roll_no = int(request.form["roll_no"])
        except ValueError:
            flash("Enrollment Number must be a valid number.", "danger")
            return redirect(url_for("add_student"))

        if Student.query.filter_by(roll_no=roll_no).first():
            flash(f"Error: Enrollment Number {roll_no} already exists! Must be unique.", "danger")
            return redirect(url_for("add_student"))
        
        name = request.form["name"]
        standard = request.form["standard"]
        attendance = request.form["attendance"]
        health_issues = request.form["health_issues"]
        assignments_pending = request.form["assignments_pending"]
        assignments_submitted = request.form["assignments_submitted"]
        remarks = request.form["remarks"]
        parent_email = request.form["parent_email"]

        new_student = Student(
            roll_no=roll_no, name=name, standard=standard, attendance=attendance,
            health_issues=health_issues, assignments_pending=assignments_pending,
            assignments_submitted=assignments_submitted, remarks=remarks,
            parent_email=parent_email
        )
        db.session.add(new_student)
        db.session.commit()
        
        # Send notification upon creation (Update type) - This will be skipped
        send_notification_email(
            parent_email, name, 'Update', 
            details=f"Student record created in the system with Roll No: {roll_no}."
        )

        flash("Student added successfully!", "success")
        return redirect(url_for("view_students"))

    return render_template("add_student.html")

# ---------- EMAIL ROUTE (Fixes BuildError) ----------
@app.route("/send-email/<int:id>")
def send_email_route(id):
    if "user_id" not in session or session.get("role") != "teacher":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("home"))
    
    student = db.session.get(Student, id) 
    
    if student:
        # Manually trigger email (which will be skipped/logged due to disabled function)
        send_notification_email(
            student.parent_email, 
            student.name, 
            'Update', 
            details="A teacher has manually triggered an email notification."
        )
        flash("Email button clicked. Check server log for INFO message (emails are currently disabled).", "info")
    else:
        flash("Student not found for email!", "danger")
        
    return redirect(url_for("view_students"))
# ----------------------------------------------------------------

@app.route("/update-student/<int:id>", methods=["GET", "POST"])
def update_student(id):
    if "user_id" not in session or session.get("role") != "teacher":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("home"))

    student = db.session.get(Student, id) # Using recommended SQLAlchemy 2.0 style
    if not student:
        flash("Student not found!", "danger")
        return redirect(url_for("view_students"))

    if request.method == "POST":
        old_remarks = student.remarks
        
        try:
            new_roll_no = int(request.form["roll_no"])
        except ValueError:
            flash("Enrollment Number must be a valid number.", "danger")
            return redirect(url_for("update_student", id=id))

        # Check for unique roll number if it's being changed
        if new_roll_no != student.roll_no and Student.query.filter_by(roll_no=new_roll_no).first():
             flash(f"Error: Enrollment Number {new_roll_no} already exists! Must be unique.", "danger")
             return redirect(url_for("update_student", id=id))

        student.roll_no = new_roll_no
        student.name = request.form["name"]
        student.standard = request.form["standard"]
        student.attendance = request.form["attendance"]
        student.health_issues = request.form["health_issues"]
        student.assignments_pending = request.form["assignments_pending"]
        student.assignments_submitted = request.form["assignments_submitted"]
        student.remarks = request.form["remarks"]
        student.parent_email = request.form["parent_email"]

        db.session.commit()
        
        notification_details = f"Remarks updated: '{old_remarks}' -> '{student.remarks}'"
        
        send_notification_email(student.parent_email, student.name, 'Update', details=notification_details)
        
        flash("Student details updated!", "success")
        return redirect(url_for("view_students"))

    return render_template("update_student.html", student=student)

@app.route("/delete-student/<int:id>")
def delete_student(id):
    if "user_id" not in session or session.get("role") != "teacher":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("home"))

    student = db.session.get(Student, id)
    if student:
        parent_email = student.parent_email
        student_name = student.name
        
        db.session.delete(student)
        db.session.commit()
        
        send_notification_email(parent_email, student_name, 'Delete')
        
        flash(f"Student {student_name} deleted successfully!", "success")
    else:
        flash("Student not found!", "danger")
    return redirect(url_for("view_students"))

@app.route("/add-complaint", methods=["GET", "POST"])
def add_complaint():
    if "user_id" not in session or session.get("role") != "teacher":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("home"))
    
    if request.method == "POST":
        roll_no = request.form["roll_no"]
        title = request.form["title"]
        description = request.form["description"]
        
        user = db.session.get(User, session["user_id"])
        student = Student.query.filter_by(roll_no=roll_no).first()

        if not student:
            flash(f"Error: Student with Roll No. {roll_no} not found.", "danger")
            return redirect(url_for("add_complaint"))

        new_complaint = Complaint(
            student_roll_no=roll_no,
            title=title,
            description=description,
            teacher_username=user.username if user else "Unknown Teacher"
        )
        
        db.session.add(new_complaint)
        db.session.commit()
        
        # Automatic Email Sending Logic (will be skipped/logged)
        complaint_details = f"""
Filer: {user.username if user else 'Unknown Teacher'}
Title: {title}
Description:
{description}
"""
        send_notification_email(
            student.parent_email, student.name, 'Complaint', details=complaint_details
        )
            
        flash("Complaint filed. (Email notification skipped.)", "success")
            
        return redirect(url_for("view_complaints"))
        
    students = Student.query.with_entities(Student.roll_no, Student.name).all()
    return render_template("add_complaint.html", students=students)

@app.route("/view-complaints")
def view_complaints():
    if "user_id" not in session or session.get("role") != "teacher":
        flash("Unauthorized access!", "danger")
        return redirect(url_for("home"))
    
    complaints = Complaint.query.order_by(Complaint.date_filed.desc()).all()
    
    return render_template("view_complaints.html", complaints=complaints)

# ---------- PARENT VIEWS ----------

@app.route("/parent-dashboard")
def parent_dashboard():
    if "parent_lookup_id" not in session or session.get("role") != "parent":
        flash("Please log in with your student's details.", "danger")
        return redirect(url_for("home"))
    
    student_id = session["parent_lookup_id"]
    student = db.session.get(Student, student_id)
    
    if not student:
        flash("Student record not found.", "danger")
        return redirect(url_for("logout"))
        
    students = [student] 
    return render_template("parent_dashboard.html", students=students)


@app.route("/parent-complaints")
def parent_complaints():
    if "parent_lookup_id" not in session or session.get("role") != "parent":
        flash("Please log in with your student's details.", "danger")
        return redirect(url_for("home"))
    
    student_roll_no = session["parent_lookup_roll_no"]
    student = Student.query.filter_by(roll_no=student_roll_no).first()

    if not student:
        flash("Student record not found.", "danger")
        return redirect(url_for("logout"))

    # Fetch complaints using the SQLAlchemy relationship
    complaints = student.complaints.order_by(Complaint.date_filed.desc()).all()
    
    return render_template("parent_complaints.html", student=student, complaints=complaints)


# ==========================
# RUN FLASK APP
# ==========================
if __name__ == "__main__":
    app.run(debug=True)