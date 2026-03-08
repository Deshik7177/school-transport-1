from flask import Flask, request, jsonify, render_template, redirect, session
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.text import MIMEText
from datetime import datetime

app = Flask(__name__)
app.secret_key = "bus_secret"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

# ==============================
# EMAIL CONFIG
# ==============================

EMAIL_ADDRESS = "pdhanadeshik2889@gmail.com"
EMAIL_PASSWORD = "kouh nluw addr lcwv"


def send_email(receiver, subject, message):

    try:

        msg = MIMEText(message)

        msg["Subject"] = subject
        msg["From"] = EMAIL_ADDRESS
        msg["To"] = receiver

        server = smtplib.SMTP("smtp.gmail.com", 587)

        server.starttls()

        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)

        server.send_message(msg)

        server.quit()

        print("Email sent to", receiver)

    except Exception as e:
        print("Email failed:", e)


# ==============================
# DATABASE MODELS
# ==============================

class Student(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(db.String(100))
    uid = db.Column(db.String(50))

    parent_name = db.Column(db.String(100))
    parent_email = db.Column(db.String(100))

    parent_username = db.Column(db.String(50))
    parent_password = db.Column(db.String(50))


class Attendance(db.Model):

    id = db.Column(db.Integer, primary_key=True)

    student_name = db.Column(db.String(100))
    status = db.Column(db.String(20))


# ==============================
# BUS DATA STORAGE
# ==============================

bus_data = {
    "lat": 0,
    "lng": 0,
    "speed": 0,
    "rash": "Driving Normal",
    "accident": "Safe",
    "students_onboard": []
}

route_history = []

# Prevent duplicate emails
last_uid = None


# ==============================
# ESP32 UPDATE ENDPOINT
# ==============================

@app.route('/update', methods=['POST'])
def update():

    global bus_data
    global route_history
    global last_uid

    data = request.json

    if data:

        bus_data = data

        # Save route history
        route_history.append({
            "lat": data["lat"],
            "lng": data["lng"]
        })

        if len(route_history) > 200:
            route_history.pop(0)

        # =========================
        # STUDENT BOARDING ALERT
        # =========================

        uid = data.get("uid")

        if uid and uid != last_uid:

            last_uid = uid

            student = Student.query.filter_by(uid=uid).first()

            if student:

                # Save attendance
                record = Attendance(
                    student_name=student.name,
                    status="Boarded"
                )

                db.session.add(record)
                db.session.commit()

                message = f"""
Smart Bus Notification

Student: {student.name}

Boarded the school bus.

Time: {datetime.now().strftime("%H:%M:%S")}

Location:
https://maps.google.com/?q={data['lat']},{data['lng']}
"""

                send_email(
                    student.parent_email,
                    "Bus Boarding Alert",
                    message
                )

        # =========================
        # ACCIDENT ALERT
        # =========================

        if data.get("accident") == "Accident Detected":

            message = f"""
EMERGENCY ALERT

Possible accident detected!

Time: {datetime.now().strftime("%H:%M:%S")}

Location:
https://maps.google.com/?q={data['lat']},{data['lng']}
"""

            # Send to all parents
            parents = Student.query.all()

            for p in parents:

                send_email(
                    p.parent_email,
                    "Bus Accident Alert",
                    message
                )

    return {"status": "ok"}


# ==============================
# DATA API FOR DASHBOARD
# ==============================

@app.route('/data')
def data():

    return jsonify({
        "bus": bus_data,
        "route": route_history
    })


# ==============================
# ADMIN LOGIN
# ==============================

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():

    if request.method == "POST":

        user = request.form["user"]
        pwd = request.form["pwd"]

        if user == "admin" and pwd == "admin":

            session["admin"] = True
            return redirect("/admin_dashboard")

    return render_template("login.html")


# ==============================
# ADMIN DASHBOARD
# ==============================

@app.route('/admin_dashboard')
def admin_dashboard():

    if "admin" not in session:
        return redirect("/admin")

    students = Student.query.all()

    return render_template("admin.html", students=students)


# ==============================
# DELETE STUDENT
# ==============================

@app.route('/delete_student/<int:id>')
def delete_student(id):

    if "admin" not in session:
        return redirect("/admin")

    student = Student.query.get(id)

    if student:
        db.session.delete(student)
        db.session.commit()

    return redirect("/admin_dashboard")


# ==============================
# REGISTER STUDENT
# ==============================

@app.route('/register_student', methods=['GET', 'POST'])
def register_student():

    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":

        name = request.form["name"]
        uid = request.form["uid"]

        parent_name = request.form["parent_name"]
        parent_email = request.form["parent_email"]

        parent_username = request.form["parent_username"]
        parent_password = request.form["parent_password"]

        new_student = Student(
            name=name,
            uid=uid,
            parent_name=parent_name,
            parent_email=parent_email,
            parent_username=parent_username,
            parent_password=parent_password
        )

        db.session.add(new_student)
        db.session.commit()

        return redirect("/admin_dashboard")

    return render_template("register_student.html")


# ==============================
# ATTENDANCE LOGS
# ==============================

@app.route('/attendance')
def attendance():

    if "admin" not in session:
        return redirect("/admin")

    records = Attendance.query.all()

    return render_template("attendance.html", attendance=records)


# ==============================
# PARENT LOGIN
# ==============================

@app.route('/', methods=['GET', 'POST'])
def parent_login():

    if request.method == "POST":

        user = request.form["username"]
        pwd = request.form["password"]

        student = Student.query.filter_by(parent_username=user).first()

        if student and student.parent_password == pwd:

            session["parent"] = student.name
            return redirect("/parent_dashboard")

    return render_template("parent_login.html")


# ==============================
# PARENT DASHBOARD
# ==============================

@app.route('/parent_dashboard')
def parent_dashboard():

    if "parent" not in session:
        return redirect("/")

    return render_template("parent_dashboard.html")


# ==============================
# LIVE BUS DASHBOARD
# ==============================

@app.route('/dashboard')
def dashboard():

    return render_template("dashboard.html")


# ==============================

if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=5000, debug=True)