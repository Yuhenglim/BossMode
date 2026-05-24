from flask import Flask, render_template, request, jsonify
from models import db, Character, Task, Message
from ai_service import generate_message
from scheduler import scheduler, run_scheduler

app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///bossmode.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)



# scheduler config
app.config["SCHEDULER_API_ENABLED"] = False

scheduler.init_app(app)

@scheduler.task("interval", id="auto_message", minutes=15, misfire_grace_time=60)
def auto_message_job():
    run_scheduler(app)

scheduler.start()

with app.app_context():
    db.create_all()


# --- Character routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/characters", methods=["POST"])
def create_character():
    data = request.json
    if not data or not all(k in data for k in ["name", "role", "personality"]):
        return jsonify({"error": "name, role, and personality are required"}), 400

    if Character.query.filter_by(name=data["name"]).first():
        return jsonify({"error": f"Character '{data['name']}' already exists"}), 409

    character = Character(
        name=data["name"],
        role=data["role"],
        picture=data.get("picture", ""),
        personality=data["personality"]
    )
    db.session.add(character)
    db.session.commit()
    return jsonify({"message": f"Character {character.name} created"}), 201

@app.route("/api/characters", methods=["GET"])
def get_characters():
    characters = Character.query.all()
    return jsonify({"characters": [c.to_dict() for c in characters]})


# --- Task routes ---
@app.route("/characters/<name>/tasks", methods=["POST"])
def add_task(name):
    character = Character.query.filter(
        Character.name.ilike(name)
    ).first_or_404(description=f"Character '{name}' not found")

    data = request.json
    if not data or not all(k in data for k in ["name", "description", "deadline"]):
        return jsonify({"error": "name, description, and deadline are required"}), 400

    task = Task(
        name=data["name"],
        description=data["description"],
        deadline=data["deadline"],
        messages_per_day=data.get("messages_per_day", 3),  # ← new, defaults to 3
        character_id=character.id
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"message": f"Task '{task.name}' added to {name}"}), 201

@app.route("/characters/<name>/tasks", methods=["GET"])
def get_tasks(name):
    character = Character.query.filter_by(name=name).first_or_404(
        description=f"Character '{name}' not found"
    )
    return jsonify({"tasks": [t.to_dict() for t in character.tasks]})

@app.route("/characters/<name>/tasks/<task_name>/complete", methods=["PATCH"])
def complete_task(name, task_name):
    character = Character.query.filter_by(name=name).first_or_404(
        description=f"Character '{name}' not found"
    )
    task = Task.query.filter_by(name=task_name, character_id=character.id).first_or_404(
        description=f"Task '{task_name}' not found"
    )
    task.is_complete = True
    db.session.commit()
    return jsonify({"message": f"'{task_name}' marked complete"})


# --- Message routes ---
@app.route("/characters/<name>/tasks/<task_name>/message", methods=["GET"])
def get_message(name, task_name):
    character = Character.query.filter_by(name=name).first_or_404(
        description=f"Character '{name}' not found"
    )
    task = Task.query.filter_by(name=task_name, character_id=character.id).first_or_404(
        description=f"Task '{task_name}' not found"
    )
    content = generate_message(character, task)
    message = Message(content=content, task_id=task.id)
    db.session.add(message)
    db.session.commit()
    return jsonify({"message": content})

@app.route("/characters/<name>/tasks/<task_name>/history", methods=["GET"])
def get_message_history(name, task_name):
    character = Character.query.filter_by(name=name).first_or_404(
        description=f"Character '{name}' not found"
    )
    task = Task.query.filter_by(name=task_name, character_id=character.id).first_or_404(
        description=f"Task '{task_name}' not found"
    )
    return jsonify({"history": [m.to_dict() for m in task.messages]})


@app.route("/characters/<name>/tasks/<task_name>/chat")
def chat(name, task_name):
    character = Character.query.filter(
        Character.name.ilike(name)
    ).first_or_404()
    task = Task.query.filter(
        Task.name.ilike(task_name),
        Task.character_id == character.id
    ).first_or_404()
    return render_template("chat.html", character=character, task=task)

@app.route("/characters/<name>")
def character_page(name):
    character = Character.query.filter_by(name=name).first_or_404()
    return render_template("tasks.html", character=character)


if __name__ == "__main__":
    app.run(debug=True)