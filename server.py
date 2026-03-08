from flask import Flask, request, jsonify, render_template, redirect, session
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.secret_key = "bus_secret"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
db = SQLAlchemy(app)

# ==============================
# DATABASE MODELS
# ==============================

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    uid = db.Column(db.String(50))
    parent_name = db.Column(db.String(100))
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
    "lat":0,
    "lng":0,
    "speed":0,
    "rash":"Driving Normal",
    "accident":"Safe",
    "students_onboard":[]
}

route_history = []


# ==============================
# ESP32 UPDATE ENDPOINT
# ==============================

@app.route('/update', methods=['POST'])
def update():

    global bus_data
    global route_history

    data = request.json

    if data:

        bus_data = data

        route_history.append({
            "lat":data["lat"],
            "lng":data["lng"]
        })

        if len(route_history) > 200:
            route_history.pop(0)

    return {"status":"ok"}


# ==============================
# DATA API FOR DASHBOARD
# ==============================

@app.route('/data')
def data():

    return jsonify({
        "bus":bus_data,
        "route":route_history
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

@app.route('/register_student', methods=['GET','POST'])
def register_student():

    if "admin" not in session:
        return redirect("/admin")

    if request.method == "POST":

        name = request.form["name"]
        uid = request.form["uid"]
        parent_name = request.form["parent_name"]
        parent_username = request.form["parent_username"]
        parent_password = request.form["parent_password"]

        new_student = Student(
            name=name,
            uid=uid,
            parent_name=parent_name,
            parent_username=parent_username,
            parent_password=parent_password
        )

        db.session.add(new_student)
        db.session.commit()

        return redirect("/admin_dashboard")

    return render_template("register_student.html")


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
# LIVE BUS DASHBOARD
# ==============================

@app.route('/dashboard')
def dashboard():

    return render_template("dashboard.html")

@app.route('/attendance')
def attendance():

    if "admin" not in session:
        return redirect("/admin")

    records = Attendance.query.all()

    return render_template("attendance.html", attendance=records)

# ==============================

if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(host="0.0.0.0", port=5000, debug=True)