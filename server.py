from flask import Flask, request, jsonify, render_template, redirect, session
from flask_sqlalchemy import SQLAlchemy
import smtplib
from email.mime.text import MIMEText
from datetime import datetime
import time

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

        server = smtplib.SMTP("smtp.gmail.com",587)

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
    time = db.Column(db.String(50))


# ==============================
# BUS DATA
# ==============================

bus_data = {
    "lat":0,
    "lng":0,
    "speed":0,
    "rash":"Driving Normal",
    "accident":"Safe",
    "roll":0,
    "pitch":0,
    "gyro":0,
    "students_onboard":[]
}

route_history = []

# RFID spam protection
last_uid = None
last_scan_time = 0


# ==============================
# ESP32 UPDATE ENDPOINT
# ==============================

@app.route('/update', methods=['POST'])
def update():

    global bus_data
    global route_history
    global last_uid
    global last_scan_time

    data = request.json

    if data:

        print("ESP32 DATA:", data)

        # Update sensor values WITHOUT deleting other fields
        bus_data["lat"] = data.get("lat",0)
        bus_data["lng"] = data.get("lng",0)
        bus_data["speed"] = data.get("speed",0)
        bus_data["rash"] = data.get("rash","Driving Normal")
        bus_data["accident"] = data.get("accident","Safe")
        bus_data["roll"] = data.get("roll",0)
        bus_data["pitch"] = data.get("pitch",0)
        bus_data["gyro"] = data.get("gyro",0)

        route_history.append({
            "lat":bus_data["lat"],
            "lng":bus_data["lng"]
        })

        if len(route_history) > 200:
            route_history.pop(0)

        uid = data.get("uid")

        if uid:

            current_time = time.time()

            # Ignore repeated scan within 5 seconds
            if uid == last_uid and current_time - last_scan_time < 5:
                return {"status":"ignored"}

            last_uid = uid
            last_scan_time = current_time

            student = Student.query.filter_by(uid=uid).first()

            if student:

                onboard = False

                for s in bus_data["students_onboard"]:
                    if s["name"] == student.name:
                        onboard = True

                if onboard:

                    # STUDENT DROPPED
                    bus_data["students_onboard"] = [
                        s for s in bus_data["students_onboard"]
                        if s["name"] != student.name
                    ]

                    status = "Dropped"

                    message = f"""
Smart Bus Notification

Student: {student.name}

Has left the school bus.

Time: {datetime.now().strftime("%H:%M:%S")}
"""

                else:

                    # STUDENT BOARDED
                    bus_data["students_onboard"].append({
                        "name": student.name
                    })

                    status = "Boarded"

                    message = f"""
Smart Bus Notification

Student: {student.name}

Boarded the school bus.

Time: {datetime.now().strftime("%H:%M:%S")}

Location:
https://maps.google.com/?q={bus_data['lat']},{bus_data['lng']}
"""

                record = Attendance(
                    student_name=student.name,
                    status=status,
                    time=datetime.now().strftime("%H:%M:%S")
                )

                db.session.add(record)
                db.session.commit()

                send_email(
                    student.parent_email,
                    "🚌 Smart School Bus Notification",
                    message
                )

        # Accident alert
        if bus_data["accident"] == "Accident Detected":

            message = f"""
🚨 EMERGENCY ALERT

Possible accident detected.

Time: {datetime.now().strftime("%H:%M:%S")}

Location:
https://maps.google.com/?q={bus_data['lat']},{bus_data['lng']}
"""

            send_email(
                EMAIL_ADDRESS,
                "🚨 Bus Accident Alert",
                message
            )

    return {"status":"ok"}


# ==============================
# DASHBOARD DATA
# ==============================

@app.route('/data')
def data():

    students = Student.query.all()

    student_list = []

    onboard_list = bus_data.get("students_onboard", [])

    for s in students:

        status = "Dropped"

        for onboard in onboard_list:
            if onboard["name"] == s.name:
                status = "Boarded"

        student_list.append({
            "name": s.name,
            "uid": s.uid,
            "status": status
        })

    return jsonify({
        "bus": bus_data,
        "route": route_history,
        "students": student_list
    })


@app.route('/get_uid')
def get_uid():

    global last_uid

    return jsonify({
        "uid": last_uid
    })

# ==============================
# ADMIN LOGIN
# ==============================

@app.route('/admin', methods=['GET','POST'])
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

    student = Student.query.get(id)

    if student:
        db.session.delete(student)
        db.session.commit()

    return redirect("/admin_dashboard")


# ==============================
# REGISTER STUDENT
# ==============================

@app.route('/register_student', methods=['GET','POST'])
def register_student():

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

    records = Attendance.query.all()

    return render_template("attendance.html", attendance=records)


# ==============================
# PARENT LOGIN
# ==============================

@app.route('/', methods=['GET','POST'])
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
# LIVE DASHBOARD
# ==============================

@app.route('/dashboard')
def dashboard():

    return render_template("dashboard.html")


# ==============================

if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=5000, debug=True)