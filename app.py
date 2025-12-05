# app.py
import os
from flask import Flask, render_template, request, redirect, url_for, flash, session, make_response
import mysql.connector
from werkzeug.security import generate_password_hash, check_password_hash
import csv
import io
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "devsecret123")

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "user": os.getenv("DB_USER", "school"),
    "password": os.getenv("DB_PASSWORD", "mahin2753"),
    "database": os.getenv("DB_NAME", "school_db"),
    "port": 3306
}

DEFAULT_PASSWORD = "123456"

def get_db():
    conn = mysql.connector.connect(**DB_CONFIG)
    return conn

def query(sql, params=None, one=False):
    conn = get_db()
    cur = conn.cursor(dictionary=True)
    cur.execute(sql, params or ())
    if sql.strip().lower().startswith("select"):
        res = cur.fetchall()
    else:
        conn.commit()
        res = None
    cur.close()
    conn.close()
    if one and res:
        return res[0]
    return res

def execute(sql, params=None):
    conn = get_db()
    cur = conn.cursor()
    cur.execute(sql, params or ())
    conn.commit()
    lastrow = cur.lastrowid
    cur.close()
    conn.close()
    return lastrow

# ------------------- Authentication -------------------
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")


@app.route("/teacher/login", methods=["GET", "POST"])
def teacher_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        row = query(
            "SELECT * FROM teacher_account ta JOIN teacher t ON ta.teacher_id=t.teacher_id WHERE ta.username=%s",
            (username,), one=True
        )

        if row:
            try:
                if check_password_hash(row['password_hash'], password):
                    session['teacher_id'] = row['teacher_id']
                    session['teacher_name'] = row['teacher_name']
                    flash("Logged in as teacher", "success")
                    return redirect(url_for("teacher_dashboard"))
            except ValueError:
                # In case password_hash is plain text
                if row['password_hash'] == password:
                    # Re-hash the plain password and update DB
                    pw_hash = generate_password_hash(password)
                    execute("UPDATE teacher_account SET password_hash=%s WHERE teacher_id=%s", (pw_hash, row['teacher_id']))
                    session['teacher_id'] = row['teacher_id']
                    session['teacher_name'] = row['teacher_name']
                    flash("Logged in as teacher", "success")
                    return redirect(url_for("teacher_dashboard"))

        flash("Invalid credentials", "danger")

    return render_template("login_teacher.html")


@app.route("/student/login", methods=["GET", "POST"])
def student_login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        row = query(
            "SELECT * FROM student_account sa JOIN student s ON sa.student_id=s.student_id WHERE sa.username=%s",
            (username,), one=True
        )

        if row:
            try:
                if check_password_hash(row['password_hash'], password):
                    session['student_id'] = row['student_id']
                    session['student_name'] = row['student_name']
                    flash("Logged in as student", "success")
                    return redirect(url_for("student_dashboard"))
            except ValueError:
                # In case password_hash is plain text
                if row['password_hash'] == password:
                    # Re-hash the plain password and update DB
                    pw_hash = generate_password_hash(password)
                    execute("UPDATE student_account SET password_hash=%s WHERE student_id=%s", (pw_hash, row['student_id']))
                    session['student_id'] = row['student_id']
                    session['student_name'] = row['student_name']
                    flash("Logged in as student", "success")
                    return redirect(url_for("student_dashboard"))

        flash("Invalid credentials", "danger")

    return render_template("login_student.html")


@app.route("/teacher/logout")
def teacher_logout():
    session.pop("teacher_id", None)
    session.pop("teacher_name", None)
    flash("Logged out", "info")
    return redirect(url_for("index"))

@app.route("/student/logout")
def student_logout():
    session.pop("student_id", None)
    session.pop("student_name", None)
    flash("Logged out", "info")
    return redirect(url_for("index"))


@app.route("/change_password", methods=["GET","POST"])
def change_password():
    if 'teacher_id' in session:
        table = "teacher_account"
        id_field = "teacher_id"
        user_id = session['teacher_id']
        redirect_url = "teacher_dashboard"
    elif 'student_id' in session:
        table = "student_account"
        id_field = "student_id"
        user_id = session['student_id']
        redirect_url = "student_dashboard"
    else:
        flash("Login first!", "danger")
        return redirect(url_for("index"))

    if request.method == "POST":
        new_pass = request.form['new_password']
        pw_hash = generate_password_hash(new_pass)
        execute(f"UPDATE {table} SET password_hash=%s WHERE {id_field}=%s", (pw_hash, user_id))
        flash("Password updated!", "success")
        return redirect(url_for(redirect_url))
    return render_template("change_password.html")

from flask import render_template, session, flash
from datetime import datetime

@app.route("/teacher/dashboard")
def teacher_dashboard():
    if not session.get("teacher_id"):
        flash("Please login first", "warning")
        return redirect(url_for("teacher_login"))

    teacher_id = session["teacher_id"]

    # Counts for cards
    students_count = query("SELECT COUNT(*) AS cnt FROM student", one=True)["cnt"]
    teachers_count = query("SELECT COUNT(*) AS cnt FROM teacher", one=True)["cnt"]
    subjects_count = query("SELECT COUNT(*) AS cnt FROM subject", one=True)["cnt"]
    exams_count = query("SELECT COUNT(*) AS cnt FROM exam", one=True)["cnt"]
    classes_count = query("SELECT COUNT(*) AS cnt FROM class", one=True)["cnt"]

    # Assignments for this teacher
    assigns = query("""
        SELECT sa.assign_id, sa.class_id, sa.subject_id, sa.teacher_id,
               c.class_name, s.subject_name, t.teacher_name
        FROM subject_assignment sa
        JOIN class c ON sa.class_id = c.class_id
        JOIN subject s ON sa.subject_id = s.subject_id
        LEFT JOIN teacher t ON sa.teacher_id = t.teacher_id
        WHERE sa.teacher_id = %s
    """, (teacher_id,))

    return render_template(
        "teacher_dashboard.html",
        students_count=students_count,
        teachers_count=teachers_count,
        subjects_count=subjects_count,
        exams_count=exams_count,
        classes_count=classes_count,
        assigns=assigns
    )

@app.route("/student/dashboard")
def student_dashboard():
    if "student_id" not in session:
        return redirect(url_for("student_login"))
    student_id = session['student_id']

    enrollment = query(
        "SELECT e.*, c.class_name, sec.section_name FROM enrollment e "
        "JOIN class c ON e.class_id=c.class_id "
        "JOIN section sec ON e.section_id=sec.section_id "
        "WHERE e.student_id=%s", (student_id,), one=True
    )

    marks = query(
        "SELECT m.*, ex.exam_name, subj.subject_name FROM mark m "
        "JOIN exam ex ON m.exam_id=ex.exam_id "
        "JOIN subject subj ON m.subject_id=subj.subject_id "
        "WHERE m.student_id=%s ORDER BY ex.exam_date DESC", (student_id,)
    )

    attendance = query(
        "SELECT * FROM attendance WHERE student_id=%s ORDER BY date DESC LIMIT 30", (student_id,)
    )

    return render_template("student_dashboard.html", enrollment=enrollment, marks=marks, attendance=attendance)


@app.route("/classes")
def classes():
    rows = query("SELECT * FROM class ORDER BY class_id DESC")
    return render_template("classes.html", classes=rows)

@app.route("/classes/add", methods=["GET","POST"])
def add_class():
    if request.method == "POST":
        name = request.form['class_name']
        execute("INSERT INTO class (class_name) VALUES (%s)", (name,))
        flash("Class added", "success")
        return redirect(url_for("classes"))
    return render_template("class_form.html", class_=None)

@app.route("/classes/edit/<int:cid>", methods=["GET","POST"])
def edit_class(cid):
    class_ = query("SELECT * FROM class WHERE class_id=%s", (cid,), one=True)
    if request.method == "POST":
        name = request.form['class_name']
        execute("UPDATE class SET class_name=%s WHERE class_id=%s", (name, cid))
        flash("Class updated", "success")
        return redirect(url_for("classes"))
    return render_template("class_form.html", class_=class_)

@app.route("/classes/delete/<int:cid>", methods=["POST"])
def delete_class(cid):
    execute("DELETE FROM class WHERE class_id=%s", (cid,))
    flash("Class deleted", "info")
    return redirect(url_for("classes"))


@app.route("/sections")
def sections():
    rows = query(
        "SELECT sec.*, c.class_name FROM section sec "
        "JOIN class c ON sec.class_id=c.class_id ORDER BY sec.section_id DESC"
    )
    return render_template("sections.html", sections=rows)

@app.route("/sections/add", methods=["GET","POST"])
def add_section():
    classes = query("SELECT * FROM class")
    if request.method == "POST":
        class_id = request.form['class_id']
        name = request.form['section_name']
        execute("INSERT INTO section (class_id, section_name) VALUES (%s,%s)", (class_id, name))
        flash("Section added", "success")
        return redirect(url_for("sections"))
    return render_template("section_form.html", section=None, classes=classes)

@app.route("/sections/edit/<int:sid>", methods=["GET","POST"])
def edit_section(sid):
    section = query("SELECT * FROM section WHERE section_id=%s", (sid,), one=True)
    classes = query("SELECT * FROM class")
    if request.method == "POST":
        class_id = request.form['class_id']
        name = request.form['section_name']
        execute("UPDATE section SET class_id=%s, section_name=%s WHERE section_id=%s", (class_id, name, sid))
        flash("Section updated", "success")
        return redirect(url_for("sections"))
    return render_template("section_form.html", section=section, classes=classes)

@app.route("/sections/delete/<int:sid>", methods=["POST"])
def delete_section(sid):
    execute("DELETE FROM section WHERE section_id=%s", (sid,))
    flash("Section deleted", "info")
    return redirect(url_for("sections"))


@app.route("/students")
def students():
    students_rows = query(
        "SELECT s.*, e.class_id, c.class_name, sec.section_name "
        "FROM student s "
        "LEFT JOIN enrollment e ON s.student_id = e.student_id "
        "LEFT JOIN class c ON e.class_id=c.class_id "
        "LEFT JOIN section sec ON e.section_id=sec.section_id "
        "ORDER BY s.student_id DESC"
    )

    classes_rows = query("SELECT * FROM class")
    sections_rows = query("SELECT * FROM section")

    return render_template(
        "students.html",
        students=students_rows,
        classes=classes_rows,
        sections=sections_rows
    )


@app.route("/students/add", methods=["GET","POST"])
def add_student():
    classes = query("SELECT * FROM class")
    sections = query("SELECT * FROM section")
    if request.method == "POST":
        name = request.form['student_name']
        dob = request.form.get('dob') or None
        gender = request.form.get('gender') or "Male"
        address = request.form.get('address')
        phone = request.form.get('phone')
        admission_no = request.form.get('admission_no')

        student_id = execute(
            "INSERT INTO student (admission_no, student_name, dob, gender, address, phone) VALUES (%s,%s,%s,%s,%s,%s)",
            (admission_no, name, dob, gender, address, phone)
        )


        username = request.form.get('username') or f"student{student_id}"
        pw_hash = generate_password_hash(DEFAULT_PASSWORD)
        execute(
            "INSERT INTO student_account (student_id, username, password_hash) VALUES (%s,%s,%s)",
            (student_id, username, pw_hash)
        )

        flash(f"Student added! Default password is '{DEFAULT_PASSWORD}'", "success")
        return redirect(url_for("students"))
    return render_template("student_form.html", student=None, classes=classes, sections=sections)


@app.route("/students/edit/<int:sid>", methods=["GET","POST"])
def edit_student(sid):
    student = query("SELECT * FROM student WHERE student_id=%s", (sid,), one=True)
    classes = query("SELECT * FROM class")
    sections = query("SELECT * FROM section")
    if request.method == "POST":
        name = request.form['student_name']
        dob = request.form.get('dob') or None
        gender = request.form.get('gender') or "Male"
        address = request.form.get('address')
        phone = request.form.get('phone')
        execute("UPDATE student SET student_name=%s, dob=%s, gender=%s, address=%s, phone=%s WHERE student_id=%s",
                (name, dob, gender, address, phone, sid))
        flash("Student updated", "success")
        return redirect(url_for("students"))
    return render_template("student_form.html", student=student, classes=classes, sections=sections)

@app.route("/students/delete/<int:sid>", methods=["POST"])
def delete_student(sid):
    execute("DELETE FROM student WHERE student_id=%s", (sid,))
    flash("Student deleted", "info")
    return redirect(url_for("students"))

@app.route("/teachers")
def teachers():
    rows = query("SELECT * FROM teacher ORDER BY teacher_id DESC")
    return render_template("teachers.html", teachers=rows)

@app.route("/teachers/add", methods=["GET","POST"])
def add_teacher():
    if request.method == "POST":
        name = request.form['teacher_name']
        phone = request.form.get('phone')
        email = request.form.get('email')
        hire = request.form.get('hire_date') or None

        tid = execute(
            "INSERT INTO teacher (teacher_name, phone, email, hire_date) VALUES (%s,%s,%s,%s)",
            (name, phone, email, hire)
        )

        username = request.form.get('username') or f"teacher{tid}"
        pw_hash = generate_password_hash(DEFAULT_PASSWORD)
        execute(
            "INSERT INTO teacher_account (teacher_id, username, password_hash) VALUES (%s,%s,%s)",
            (tid, username, pw_hash)
        )

        flash(f"Teacher added! Default password is '{DEFAULT_PASSWORD}'", "success")
        return redirect(url_for("teachers"))
    return render_template("teacher_form.html", teacher=None)


@app.route("/teachers/edit/<int:tid>", methods=["GET","POST"])
def edit_teacher(tid):
    teacher = query("SELECT * FROM teacher WHERE teacher_id=%s", (tid,), one=True)
    if request.method == "POST":
        name = request.form['teacher_name']
        phone = request.form.get('phone')
        email = request.form.get('email')
        hire = request.form.get('hire_date') or None
        execute("UPDATE teacher SET teacher_name=%s, phone=%s, email=%s, hire_date=%s WHERE teacher_id=%s",
                (name, phone, email, hire, tid))
        flash("Teacher updated", "success")
        return redirect(url_for("teachers"))
    return render_template("teacher_form.html", teacher=teacher)

@app.route("/teachers/delete/<int:tid>", methods=["POST"])
def delete_teacher(tid):
    execute("DELETE FROM teacher WHERE teacher_id=%s", (tid,))
    flash("Teacher deleted", "info")
    return redirect(url_for("teachers"))

@app.route("/subjects")
def subjects():
    subs = query(
        "SELECT s.*, "
        "(SELECT GROUP_CONCAT(CONCAT(c.class_name,'-',t.teacher_name) SEPARATOR '; ') "
        "FROM subject_assignment sa "
        "JOIN class c ON sa.class_id=c.class_id "
        "LEFT JOIN teacher t ON sa.teacher_id=t.teacher_id "
        "WHERE sa.subject_id = s.subject_id) AS assigned_to "
        "FROM subject s ORDER BY s.subject_id"
    )
    classes = query("SELECT * FROM class")
    teachers = query("SELECT * FROM teacher")
    return render_template("subjects.html", subjects=subs, classes=classes, teachers=teachers)

@app.route("/subjects/add", methods=["POST"])
def add_subject():
    name = request.form['subject_name']
    execute("INSERT INTO subject (subject_name) VALUES (%s)", (name,))
    flash("Subject added", "success")
    return redirect(url_for("subjects"))

@app.route("/subjects/edit/<int:sid>", methods=["GET","POST"])
def edit_subject(sid):
    subject = query("SELECT * FROM subject WHERE subject_id=%s", (sid,), one=True)
    if request.method == "POST":
        name = request.form['subject_name']
        execute("UPDATE subject SET subject_name=%s WHERE subject_id=%s", (name, sid))
        flash("Subject updated", "success")
        return redirect(url_for("subjects"))
    return render_template("subject_form.html", subject=subject)

@app.route("/subjects/delete/<int:sid>", methods=["POST"])
def delete_subject(sid):
    execute("DELETE FROM subject WHERE subject_id=%s", (sid,))
    flash("Subject deleted", "info")
    return redirect(url_for("subjects"))

@app.route("/assign_subject", methods=["POST"])
def assign_subject():
    class_id = request.form['class_id']
    subject_id = request.form['subject_id']
    teacher_id = request.form.get('teacher_id') or None

    existing = query("SELECT * FROM subject_assignment WHERE class_id=%s AND subject_id=%s",
                     (class_id, subject_id), one=True)
    if existing:
        execute("UPDATE subject_assignment SET teacher_id=%s WHERE assign_id=%s",
                (teacher_id, existing['assign_id']))
    else:
        execute("INSERT INTO subject_assignment (class_id, subject_id, teacher_id) VALUES (%s,%s,%s)",
                (class_id, subject_id, teacher_id))
    flash("Subject assigned", "success")
    return redirect(url_for("subjects"))


@app.route("/exams")
def exams():
    exams = query("SELECT ex.*, c.class_name FROM exam ex JOIN class c ON ex.class_id=c.class_id ORDER BY ex.exam_date DESC")
    classes = query("SELECT * FROM class")
    return render_template("exams.html", exams=exams, classes=classes)

@app.route("/exams/add", methods=["GET","POST"])
def add_exam():
    classes = query("SELECT * FROM class")
    if request.method == "POST":
        name = request.form['exam_name']
        d = request.form.get('exam_date') or None
        class_id = request.form.get('class_id')
        maxm = request.form.get('max_marks') or 100
        execute("INSERT INTO exam (exam_name, exam_date, class_id, max_marks) VALUES (%s,%s,%s,%s)",
                (name, d, class_id, maxm))
        flash("Exam created", "success")
        return redirect(url_for("exams"))
    return render_template("exam_form.html", classes=classes, exam=None)

@app.route("/exams/edit/<int:eid>", methods=["GET","POST"])
def edit_exam(eid):
    exam = query("SELECT * FROM exam WHERE exam_id=%s", (eid,), one=True)
    classes = query("SELECT * FROM class")
    if request.method == "POST":
        name = request.form['exam_name']
        d = request.form.get('exam_date') or None
        class_id = request.form.get('class_id')
        maxm = request.form.get('max_marks') or 100
        execute("UPDATE exam SET exam_name=%s, exam_date=%s, class_id=%s, max_marks=%s WHERE exam_id=%s",
                (name, d, class_id, maxm, eid))
        flash("Exam updated", "success")
        return redirect(url_for("exams"))
    return render_template("exam_form.html", classes=classes, exam=exam)

@app.route("/exams/delete/<int:eid>", methods=["POST"])
def delete_exam(eid):
    execute("DELETE FROM exam WHERE exam_id=%s", (eid,))
    flash("Exam deleted", "info")
    return redirect(url_for("exams"))

@app.route("/marks/<int:exam_id>")
def marks(exam_id):
    exam = query("SELECT * FROM exam WHERE exam_id=%s", (exam_id,), one=True)
    if not exam:
        flash("Exam not found", "danger")
        return redirect(url_for("exams"))

    if 'student_id' in session:
        marks = query("""
            SELECT m.*, subj.subject_name
            FROM mark m
            JOIN subject subj ON m.subject_id=subj.subject_id
            WHERE m.exam_id=%s AND m.student_id=%s
        """, (exam_id, session['student_id']))
    else:
        marks = query("""
            SELECT m.*, s.student_name, subj.subject_name, s.admission_no
            FROM mark m
            JOIN student s ON m.student_id=s.student_id
            JOIN subject subj ON m.subject_id=subj.subject_id
            WHERE m.exam_id=%s
            ORDER BY s.student_name
        """, (exam_id,))

    students = query("SELECT s.* FROM student s JOIN enrollment e ON s.student_id=e.student_id WHERE e.class_id=%s",
                     (exam['class_id'],))
    subjects = query("SELECT * FROM subject")
    return render_template("marks.html", exam=exam, marks=marks, students=students, subjects=subjects)


@app.route("/marks/add", methods=["POST"])
def add_mark():
    if 'student_id' in session:
        flash("Students cannot give or edit marks", "danger")
        return redirect(url_for("exams"))

    exam_id = request.form['exam_id']
    student_id = request.form['student_id']
    subject_id = request.form['subject_id']
    marks = request.form.get('marks_obtained') or None

    existing = query("SELECT * FROM mark WHERE exam_id=%s AND student_id=%s AND subject_id=%s",
                     (exam_id, student_id, subject_id), one=True)
    if existing:
        execute("UPDATE mark SET marks_obtained=%s WHERE mark_id=%s", (marks, existing['mark_id']))
    else:
        execute("INSERT INTO mark (exam_id, student_id, subject_id, marks_obtained) VALUES (%s,%s,%s,%s)",
                (exam_id, student_id, subject_id, marks))

    flash("Mark recorded", "success")
    return redirect(url_for("marks", exam_id=exam_id))


@app.route("/marks/download/<int:exam_id>")
def download_marks(exam_id):
    exam = query("SELECT * FROM exam WHERE exam_id=%s", (exam_id,), one=True)
    if not exam:
        flash("Exam not found", "danger")
        return redirect(url_for("exams"))

    # Students → only their marks
    if 'student_id' in session:
        marks = query("""
            SELECT m.*, s.admission_no, s.student_name, subj.subject_name
            FROM mark m
            JOIN student s ON m.student_id=s.student_id
            JOIN subject subj ON m.subject_id=subj.subject_id
            WHERE m.exam_id=%s AND m.student_id=%s
        """, (exam_id, session['student_id']))
    else:
        marks = query("""
            SELECT m.*, s.admission_no, s.student_name, subj.subject_name
            FROM mark m
            JOIN student s ON m.student_id=s.student_id
            JOIN subject subj ON m.subject_id=subj.subject_id
            WHERE m.exam_id=%s
            ORDER BY s.student_name
        """, (exam_id,))

    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Admission No", "Student", "Subject", "Marks Obtained", "Exam"])
    for r in marks:
        cw.writerow([r.get('admission_no'), r.get('student_name'), r.get('subject_name'), r.get('marks_obtained'), exam['exam_name']])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=marks_exam_{exam_id}.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@app.route("/teacher/marks/<int:class_id>/<int:subject_id>")
def teacher_marks_select_exam(class_id, subject_id):
    if "teacher_id" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("teacher_login"))

    assign_check = query(
        "SELECT * FROM subject_assignment WHERE class_id=%s AND subject_id=%s AND (teacher_id=%s OR teacher_id IS NULL)",
        (class_id, subject_id, session['teacher_id']), one=True
    )
    if not assign_check:

        flash("You are not assigned to this subject/class", "danger")
        return redirect(url_for("teacher_dashboard"))

    exams = query("SELECT * FROM exam WHERE class_id=%s ORDER BY exam_date DESC", (class_id,))
    subject = query("SELECT subject_name FROM subject WHERE subject_id=%s", (subject_id,), one=True)
    class_row = query("SELECT class_name FROM class WHERE class_id=%s", (class_id,), one=True)

    return render_template("teacher_marks_select_exam.html",
                           exams=exams,
                           subject=subject,
                           class_row=class_row,
                           class_id=class_id,
                           subject_id=subject_id)

@app.route("/teacher/marks/manage/<int:exam_id>/<int:subject_id>", methods=["GET","POST"])
def teacher_manage_marks(exam_id, subject_id):
    if "teacher_id" not in session:
        flash("Please login first", "warning")
        return redirect(url_for("teacher_login"))

    exam = query("SELECT * FROM exam WHERE exam_id=%s", (exam_id,), one=True)
    if not exam:
        flash("Exam not found", "danger")
        return redirect(url_for("teacher_dashboard"))

    subject = query("SELECT * FROM subject WHERE subject_id=%s", (subject_id,), one=True)
    if not subject:
        flash("Subject not found", "danger")
        return redirect(url_for("teacher_dashboard"))

    assign_check = query(
        "SELECT * FROM subject_assignment WHERE class_id=%s AND subject_id=%s AND teacher_id=%s",
        (exam['class_id'], subject_id, session['teacher_id']), one=True
    )
    if not assign_check:
        flash("You are not assigned to enter marks for this class/subject", "danger")
        return redirect(url_for("teacher_dashboard"))

    students = query("""
        SELECT st.student_id, st.student_name
        FROM student st
        JOIN enrollment e ON st.student_id=e.student_id
        WHERE e.class_id=%s
        ORDER BY st.student_name
    """, (exam['class_id'],))

    existing_marks = query("""
        SELECT student_id, marks_obtained, mark_id
        FROM mark
        WHERE exam_id=%s AND subject_id=%s
    """, (exam_id, subject_id)) or []

    mark_map = {m['student_id']: {'marks': m['marks_obtained'], 'mark_id': m.get('mark_id')} for m in existing_marks}

    if request.method == "POST":
        for st in students:
            sid = st['student_id']
            marks = request.form.get(f"marks_{sid}") or None

            if marks == "":
                marks = None

            existing_row = query("""
                SELECT mark_id FROM mark WHERE exam_id=%s AND student_id=%s AND subject_id=%s
            """, (exam_id, sid, subject_id), one=True)

            if existing_row:
                execute("UPDATE mark SET marks_obtained=%s WHERE mark_id=%s", (marks, existing_row['mark_id']))
            else:
                execute("INSERT INTO mark (exam_id, student_id, subject_id, marks_obtained) VALUES (%s,%s,%s,%s)",
                        (exam_id, sid, subject_id, marks))

        flash("Marks updated!", "success")
        return redirect(url_for("teacher_dashboard"))

    return render_template("teacher_manage_marks.html",
                           exam=exam,
                           subject=subject,
                           students=students,
                           mark_map=mark_map)

@app.route("/attendance/<int:class_id>", methods=["GET","POST"])
def attendance(class_id):
    class_info = query("SELECT * FROM class WHERE class_id=%s", (class_id,), one=True)
    students = query("SELECT st.*, e.enrollment_id FROM student st JOIN enrollment e ON st.student_id=e.student_id WHERE e.class_id=%s",
                     (class_id,))
    if request.method == "POST":
        date = request.form.get('date') or datetime.today().date()
        for sid in request.form.getlist('student_id'):
            status = request.form.get(f"status_{sid}") or "Present"
            existing = query("SELECT * FROM attendance WHERE date=%s AND student_id=%s", (date, sid), one=True)
            if existing:
                execute("UPDATE attendance SET status=%s WHERE attendance_id=%s", (status, existing['attendance_id']))
            else:
                enr = query("SELECT * FROM enrollment WHERE student_id=%s AND class_id=%s", (sid, class_id), one=True)
                section_id = enr['section_id'] if enr else None
                execute("INSERT INTO attendance (date, student_id, class_id, section_id, status) VALUES (%s,%s,%s,%s,%s)",
                        (date, sid, class_id, section_id, status))
        flash("Attendance saved", "success")
        return redirect(url_for("attendance", class_id=class_id))

    today = datetime.today().date()
    attendance_rows = query("SELECT * FROM attendance WHERE date=%s AND class_id=%s", (today, class_id))
    attendance_map = {r['student_id']: r for r in attendance_rows} if attendance_rows else {}
    return render_template("attendance.html", class_info=class_info, students=students, attendance_map=attendance_map, today=today)

@app.route("/attendance/download/<int:class_id>")
def download_attendance(class_id):
    rows = query(
        "SELECT a.*, s.admission_no, s.student_name, c.class_name, sec.section_name "
        "FROM attendance a "
        "JOIN student s ON a.student_id=s.student_id "
        "JOIN class c ON a.class_id=c.class_id "
        "JOIN section sec ON a.section_id=sec.section_id "
        "WHERE a.class_id=%s ORDER BY a.date DESC LIMIT 1000", (class_id,)
    )
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Date", "Admission No", "Student", "Class", "Section", "Status"])
    for r in rows:
        cw.writerow([r['date'], r['admission_no'], r['student_name'], r['class_name'], r['section_name'], r['status']])
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = f"attachment; filename=attendance_class_{class_id}.csv"
    output.headers["Content-type"] = "text/csv"
    return output


@app.route("/enrollments")
def enrollments():
    rows = query(
        "SELECT e.enrollment_id, s.student_name, c.class_name, sec.section_name "
        "FROM enrollment e "
        "JOIN student s ON e.student_id=s.student_id "
        "JOIN class c ON e.class_id=c.class_id "
        "JOIN section sec ON e.section_id=sec.section_id "
        "ORDER BY e.enrollment_id DESC"
    )
    return render_template("enrollment.html", enrollments=rows)


@app.route("/enrollments/add", methods=["GET","POST"])
def enrollment_form():
    students = query("SELECT student_id, student_name FROM student")
    classes = query("SELECT class_id, class_name FROM class")
    sections = query("SELECT section_id, section_name FROM section")

    if request.method == "POST":
        student_id = request.form.get("student_id")
        class_id = request.form.get("class_id")
        section_id = request.form.get("section_id")

        if not all([student_id, class_id, section_id]):
            flash("All fields are required", "danger")
            return redirect(url_for("enrollment_form"))

        execute(
            "INSERT INTO enrollment (student_id, class_id, section_id) VALUES (%s,%s,%s)",
            (student_id, class_id, section_id)
        )
        flash("Student enrolled successfully!", "success")
        return redirect(url_for("enrollments"))

    return render_template("enrollment_form.html", students=students, classes=classes, sections=sections)


@app.route("/enrollments/delete/<int:enr_id>", methods=["POST"])
def delete_enrollment(enr_id):
    execute("DELETE FROM enrollment WHERE enrollment_id=%s", (enr_id,))
    flash("Enrollment deleted", "info")
    return redirect(url_for("enrollments"))


if __name__ == "__main__":
    app.run(debug=True)
