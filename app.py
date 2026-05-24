from dotenv import load_dotenv
load_dotenv()

from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, Character, Task, Message
from ai_service import generate_message, generate_reply
from scheduler import scheduler, run_scheduler
import os

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-key")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

database_url = os.environ.get("DATABASE_URL", "sqlite:///bossmode.db")
if database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql://", 1)
app.config["SQLALCHEMY_DATABASE_URI"] = database_url

db.init_app(app)

# Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Scheduler
app.config["SCHEDULER_API_ENABLED"] = False
scheduler.init_app(app)

@scheduler.task("interval", id="auto_message", minutes=15, misfire_grace_time=60)
def auto_message_job():
    run_scheduler(app)

scheduler.start()

with app.app_context():
    db.create_all()


# ── Auth routes ───────────────────────────────────────────────
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":
        data = request.json
        if User.query.filter_by(email=data["email"]).first():
            return jsonify({"error": "Email already registered"}), 409

        user = User(
            email=data["email"],
            password=generate_password_hash(data["password"]),
            name=data["name"]
        )
        db.session.add(user)
        db.session.commit()
        login_user(user)
        return jsonify({"message": "Account created"}), 201

    return render_template("auth.html", mode="signup")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.json
        user = User.query.filter_by(email=data["email"]).first()
        if not user or not check_password_hash(user.password, data["password"]):
            return jsonify({"error": "Invalid email or password"}), 401

        login_user(user)
        return jsonify({"message": "Logged in"}), 200

    return render_template("auth.html", mode="login")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))


# ── Main page ─────────────────────────────────────────────────
@app.route("/")
@login_required
def index():
    return render_template("index.html", user=current_user)


# ── Character routes ──────────────────────────────────────────
@app.route("/api/characters", methods=["POST"])
@login_required
def create_character():
    data = request.json
    if not data or not all(k in data for k in ["name", "role", "personality"]):
        return jsonify({"error": "name, role, and personality are required"}), 400

    character = Character(
        name=data["name"],
        role=data["role"],
        picture=data.get("picture", ""),
        personality=data["personality"],
        user_id=current_user.id
    )
    db.session.add(character)
    db.session.commit()
    return jsonify(character.to_dict()), 201

@app.route("/api/characters", methods=["GET"])
@login_required
def get_characters():
    characters = Character.query.filter_by(user_id=current_user.id).all()
    return jsonify({"characters": [c.to_dict() for c in characters]})


# ── Task routes ───────────────────────────────────────────────
@app.route("/api/characters/<int:character_id>/tasks", methods=["POST"])
@login_required
def add_task(character_id):
    character = Character.query.filter_by(id=character_id, user_id=current_user.id).first_or_404()
    data = request.json
    if not data or not all(k in data for k in ["name", "description", "deadline"]):
        return jsonify({"error": "name, description, and deadline are required"}), 400

    task = Task(
        name=data["name"],
        description=data["description"],
        deadline=data["deadline"],
        messages_per_day=data.get("messages_per_day", 3),
        character_id=character.id
    )
    db.session.add(task)
    db.session.commit()
    return jsonify(task.to_dict()), 201

@app.route("/api/characters/<int:character_id>/tasks", methods=["GET"])
@login_required
def get_tasks(character_id):
    character = Character.query.filter_by(id=character_id, user_id=current_user.id).first_or_404()
    return jsonify({"tasks": [t.to_dict() for t in character.tasks]})

@app.route("/api/tasks/<int:task_id>/complete", methods=["PATCH"])
@login_required
def complete_task(task_id):
    task = Task.query.join(Character).filter(
        Task.id == task_id,
        Character.user_id == current_user.id
    ).first_or_404()
    task.is_complete = True
    db.session.commit()
    return jsonify({"message": "Task marked complete"})


# ── Message routes ────────────────────────────────────────────
@app.route("/api/tasks/<int:task_id>/message", methods=["GET"])
@login_required
def get_message(task_id):
    task = Task.query.join(Character).filter(
        Task.id == task_id,
        Character.user_id == current_user.id
    ).first_or_404()

    content = generate_message(task.character, task)
    message = Message(content=content, task_id=task.id, is_user=False)
    db.session.add(message)
    db.session.commit()
    return jsonify(message.to_dict())

@app.route("/api/tasks/<int:task_id>/reply", methods=["POST"])
@login_required
def user_reply(task_id):
    task = Task.query.join(Character).filter(
        Task.id == task_id,
        Character.user_id == current_user.id
    ).first_or_404()

    data = request.json
    user_text = data.get("message", "").strip()
    if not user_text:
        return jsonify({"error": "Message is empty"}), 400

    # Save user message
    user_msg = Message(content=user_text, task_id=task.id, is_user=True)
    db.session.add(user_msg)
    db.session.commit()

    # Generate character reply
    reply_content = generate_reply(task.character, task, user_text)
    reply_msg = Message(content=reply_content, task_id=task.id, is_user=False)
    db.session.add(reply_msg)
    db.session.commit()

    return jsonify({
        "user_message": user_msg.to_dict(),
        "reply": reply_msg.to_dict()
    })

@app.route("/api/tasks/<int:task_id>/history", methods=["GET"])
@login_required
def get_history(task_id):
    task = Task.query.join(Character).filter(
        Task.id == task_id,
        Character.user_id == current_user.id
    ).first_or_404()
    return jsonify({"history": [m.to_dict() for m in task.messages]})


# ── Edit & delete character ───────────────────────────────────
@app.route("/api/characters/<int:character_id>", methods=["PATCH"])
@login_required
def edit_character(character_id):
    character = Character.query.filter_by(id=character_id, user_id=current_user.id).first_or_404()
    data = request.json
    if "name"        in data: character.name        = data["name"]
    if "role"        in data: character.role        = data["role"]
    if "personality" in data: character.personality = data["personality"]
    if "picture"     in data: character.picture     = data["picture"]
    db.session.commit()
    return jsonify(character.to_dict())

@app.route("/api/characters/<int:character_id>", methods=["DELETE"])
@login_required
def delete_character(character_id):
    character = Character.query.filter_by(id=character_id, user_id=current_user.id).first_or_404()
    db.session.delete(character)
    db.session.commit()
    return jsonify({"message": "Character deleted"})


# ── Edit & delete task ────────────────────────────────────────
@app.route("/api/tasks/<int:task_id>", methods=["PATCH"])
@login_required
def edit_task(task_id):
    task = Task.query.join(Character).filter(
        Task.id == task_id,
        Character.user_id == current_user.id
    ).first_or_404()
    data = request.json
    if "name"             in data: task.name             = data["name"]
    if "description"      in data: task.description      = data["description"]
    if "deadline"         in data: task.deadline         = data["deadline"]
    if "messages_per_day" in data: task.messages_per_day = data["messages_per_day"]
    db.session.commit()
    return jsonify(task.to_dict())

@app.route("/api/tasks/<int:task_id>", methods=["DELETE"])
@login_required
def delete_task(task_id):
    task = Task.query.join(Character).filter(
        Task.id == task_id,
        Character.user_id == current_user.id
    ).first_or_404()
    db.session.delete(task)
    db.session.commit()
    return jsonify({"message": "Task deleted"})


# ── Character profile page ────────────────────────────────────
@app.route("/characters/<int:character_id>")
@login_required
def character_profile(character_id):
    character = Character.query.filter_by(id=character_id, user_id=current_user.id).first_or_404()
    tasks = Task.query.filter_by(character_id=character_id).all()
    return render_template("profile.html", character=character, tasks=tasks, user=current_user)

if __name__ == "__main__":
    app.run(debug=False)