import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, session

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dynamo_secret")

# ✅ DATABASE CONFIG
# Use an absolute path for the database to avoid issues on different environments
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, "database.db")

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # This allows accessing columns by name
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT
        )
    """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            filename TEXT,
            upload_time TEXT
        )
    """
    )

    # Stores login/logout history and total work duration per session
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            login_time TEXT,
            logout_time TEXT,
            duration_seconds INTEGER
        )
    """
    )

    conn.commit()
    conn.close()

# Initialize database on startup
init_db()

# 7 Members + Admin hardcoded (used for auth + admin analytics)
users = {
    "Neha29": "292006",
    "Harish_Gokul": "Gokul@2026",
    "Manoj_prabakaran": "Mano2026",
    "Karthiga_priya": "Karthiga@2026",
    "Breny_cindrella": "Breny@2026",
    "Lincee_hillaria": "Lincee@2026",
    "Shankar_nath": "Shanakar@2026",
    "admin": "Future_Techy@2030",
}


# Landing Page (Home)
@app.route("/")
def home():
    return "App is working"


# Login Page + Logic
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    username = request.form.get("username")
    password = request.form.get("password")

    # 🔐 Hardcoded login check (demo). Credentials are defined in `users`.
    if username in users and users[username] == password:
        session["user"] = username
        session["login_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if username == "admin":
            return redirect("/admin")
        return redirect("/dashboard")

    return render_template("login.html", error="Invalid username or password. Try again.")
        
# Dashboard for normal members
@app.route("/dashboard")
def dashboard():
    # Must be logged in and not admin
    if "user" in session and session["user"] != "admin":
        current_user = session["user"]

        conn = get_db_connection()
        cursor = conn.cursor()

        # User's uploaded files
        cursor.execute(
            "SELECT id, filename, upload_time FROM files WHERE username = ?",
            (current_user,),
        )
        files = cursor.fetchall()

        # Work sessions for this user (latest first)
        cursor.execute(
            """
            SELECT login_time, logout_time, duration_seconds
            FROM sessions
            WHERE username = ?
            ORDER BY id DESC
            LIMIT 10
        """,
            (current_user,),
        )
        work_history = cursor.fetchall()

        # Total working time in seconds
        cursor.execute(
            "SELECT COALESCE(SUM(duration_seconds), 0) FROM sessions WHERE username = ?",
            (current_user,),
        )
        total_seconds_row = cursor.fetchone()
        total_seconds = total_seconds_row[0] if total_seconds_row and total_seconds_row[0] else 0

        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        total_work_time = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

        conn.close()

        return render_template(
            "dashboard.html",
            user=current_user,
            files=files,
            total_work_time=total_work_time,
            work_history=work_history,
            domain=session.get("domain", "Not set"),
        )

        conn.close()

    return redirect("/login")

# Admin Dashboard

@app.route("/admin")
def admin():
    if "user" in session and session["user"] == "admin":
        conn = get_db_connection()
        cursor = conn.cursor()

        # All uploaded files (for file management)
        cursor.execute("SELECT id, username, filename, upload_time FROM files")
        files = cursor.fetchall()

        # Work analytics per member
        member_usernames = [u for u in users.keys() if u != "admin"]
        members_stats = []
        total_work_seconds_all = 0
        total_files_all = 0

        for username in member_usernames:
            # Total work duration
            cursor.execute(
                "SELECT COALESCE(SUM(duration_seconds), 0) FROM sessions WHERE username = ?",
                (username,),
            )
            row = cursor.fetchone()
            total_seconds = row[0] if row and row[0] else 0
            total_work_seconds_all += total_seconds

            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60

            # Last login/logout
            cursor.execute(
                """
                SELECT login_time, logout_time
                FROM sessions
                WHERE username = ?
                ORDER BY id DESC
                LIMIT 1
            """,
                (username,),
            )
            last_session = cursor.fetchone()
            last_login = last_session[0] if last_session else None
            last_logout = last_session[1] if last_session else None

            # File count
            cursor.execute(
                "SELECT COUNT(*) FROM files WHERE username = ?", (username,)
            )
            file_count_row = cursor.fetchone()
            file_count = file_count_row[0] if file_count_row else 0
            total_files_all += file_count

            members_stats.append(
                {
                    "username": username,
                    "total_hours": hours,
                    "total_minutes": minutes,
                    "file_count": file_count,
                    "last_login": last_login,
                    "last_logout": last_logout,
                }
            )

        # Recent sessions across all members
        cursor.execute(
            """
            SELECT username, login_time, logout_time, duration_seconds
            FROM sessions
            ORDER BY id DESC
            LIMIT 20
        """
        )
        recent_sessions = cursor.fetchall()

        conn.close()

        total_members = len(member_usernames)
        total_hours_all = total_work_seconds_all / 3600 if total_work_seconds_all else 0

        return render_template(
            "admin.html",
            files=files,
            members_stats=members_stats,
            total_members=total_members,
            total_hours_all=round(total_hours_all, 2),
            total_files_all=total_files_all,
            recent_sessions=recent_sessions,
        )

    return redirect("/login")

@app.route("/admin_files")
def admin_files():
    if "user" in session and session["user"] == "admin":

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT id, username, filename, upload_time FROM files")
        files = cursor.fetchall()

        conn.close()

        return render_template("admin_files.html", files=files)

    return redirect("/")

@app.route("/admin_delete/<int:file_id>")
def admin_delete(file_id):
    if "user" in session and session["user"] == "admin":

        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT username, filename FROM files WHERE id = ?", (file_id,))
        file = cursor.fetchone()

        if file:
            username, filename = file
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], username, filename)

            if os.path.exists(filepath):
                os.remove(filepath)

            cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
            conn.commit()

        conn.close()

        return redirect("/admin_files")

    return redirect("/")

@app.route("/update_work", methods=["POST"])
def update_work():
    if "user" in session and session["user"] != "admin":
        domain = request.form.get("domain", "").strip()
        if domain:
            session["domain"] = domain
        return redirect("/dashboard")
    return redirect("/login")

# Logout + Work Time Tracking
@app.route("/logout")
def logout():
    if "user" in session and "login_time" in session:
        username = session["user"]
        login_time_str = session["login_time"]
        login_time = datetime.strptime(login_time_str, "%Y-%m-%d %H:%M:%S")
        logout_time = datetime.now()
        duration = logout_time - login_time
        duration_seconds = int(duration.total_seconds())

        # Log work session into database for analytics
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO sessions (username, login_time, logout_time, duration_seconds)
            VALUES (?, ?, ?, ?)
        """,
            (
                username,
                login_time_str,
                logout_time.strftime("%Y-%m-%d %H:%M:%S"),
                duration_seconds,
            ),
        )
        conn.commit()
        conn.close()

        # Optional: keep text log for backup
        log_path = os.path.join(BASE_DIR, "work_log.txt")
        with open(log_path, "a") as file:
            domain = session.get("domain", "No Domain")
            file.write(
                f"User: {username} | Domain: {domain} | Worked Time: {duration}\n"
            )

        session.clear()

    return redirect("/")


UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER


@app.route("/upload_file", methods=["POST"])
def upload_file():
    if "user" in session and session["user"] != "admin":
        user_folder = os.path.join(app.config["UPLOAD_FOLDER"], session["user"])
        os.makedirs(user_folder, exist_ok=True)

        f = request.files["workfile"]

        if not f or f.filename == "":
            return redirect("/dashboard")

        filepath = os.path.join(user_folder, f.filename)
        f.save(filepath)

        # Store file metadata in database
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO files (username, filename, upload_time)
            VALUES (?, ?, ?)
        """,
            (
                session["user"],
                f.filename,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            ),
        )

        conn.commit()
        conn.close()

        session["uploaded"] = True
        return redirect("/dashboard")

    return redirect("/login")
# -----------------------------------------------

@app.route("/my_files")
def my_files():
    if "user" in session and session["user"] != "admin":
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT id, filename, upload_time FROM files WHERE username = ?",
            (session["user"],),
        )
        files = cursor.fetchall()

        conn.close()

        return render_template("my_files.html", files=files)

    return redirect("/login")


@app.route("/delete_file/<int:file_id>")
def delete_file(file_id):
    if "user" in session and session["user"] != "admin":
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT filename FROM files WHERE id = ?", (file_id,))
        file = cursor.fetchone()

        if file:
            filename = file[0]
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], session["user"], filename)

            if os.path.exists(filepath):
                os.remove(filepath)

            cursor.execute("DELETE FROM files WHERE id = ?", (file_id,))
            conn.commit()

        conn.close()
        return redirect("/my_files")

    return redirect("/login")

if __name__ == "__main__":
    app.run(debug=True)