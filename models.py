from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Character(db.Model):
    __tablename__ = "characters"

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), unique=True, nullable=False)
    role        = db.Column(db.String(100), nullable=False)
    picture     = db.Column(db.String(255))
    personality = db.Column(db.Text, nullable=False)

    tasks = db.relationship("Task", backref="character", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":          self.id,
            "name":        self.name,
            "role":        self.role,
            "picture":     self.picture,
            "personality": self.personality,
        }



class Message(db.Model):
    __tablename__ = "messages"

    id         = db.Column(db.Integer, primary_key=True)
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False)

    def to_dict(self):
        return {
            "id":         self.id,
            "content":    self.content,
            "created_at": self.created_at.isoformat(),
        }
    
class Task(db.Model):
    __tablename__ = "tasks"

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(100), nullable=False)
    description     = db.Column(db.Text)
    deadline        = db.Column(db.String(20), nullable=False)
    is_complete     = db.Column(db.Boolean, default=False, nullable=False)
    messages_per_day = db.Column(db.Integer, default=3, nullable=False)  # ← new

    character_id = db.Column(db.Integer, db.ForeignKey("characters.id"), nullable=False)
    messages     = db.relationship("Message", backref="task", lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "id":               self.id,
            "name":             self.name,
            "description":      self.description,
            "deadline":         self.deadline,
            "is_complete":      self.is_complete,
            "messages_per_day": self.messages_per_day,
        }