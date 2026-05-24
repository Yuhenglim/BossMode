from flask_apscheduler import APScheduler
from datetime import datetime
import random

scheduler = APScheduler()

def is_active_hours():
    now = datetime.now()
    weekday = now.weekday()  # 0=Monday, 6=Sunday
    hour = now.hour

    if weekday < 5:  # weekdays
        return 18 <= hour <= 23
    else:  # weekends
        return 9 <= hour <= 23

def get_interval_minutes(task, default_daily_count=3):
    today = datetime.today().date()
    deadline = datetime.strptime(task.deadline, "%Y-%m-%d").date()
    days_left = (deadline - today).days

    if days_left <= 0 or days_left == 1:
        return 60           # urgent — every 1 hour
    elif days_left == 2:
        return 90           # every 1.5 hours
    elif days_left == 3:
        return 120          # every 2 hours
    elif days_left == 4:
        return 150          # every 2.5 hours
    else:
        # user-defined: spread messages evenly across active hours
        # weekday active window = 5hrs (6PM-11PM)
        # weekend active window = 14hrs (9AM-11PM)
        now = datetime.now()
        is_weekend = now.weekday() >= 5
        active_hours = 14 if is_weekend else 5
        active_minutes = active_hours * 60
        return active_minutes // default_daily_count

def run_scheduler(app, default_daily_count=3):
    from models import Task, Message, db
    from ai_service import generate_message

    with app.app_context():
        if not is_active_hours():
            return

        incomplete_tasks = Task.query.filter_by(is_complete=False).all()

        for task in incomplete_tasks:
            interval = get_interval_minutes(task, default_daily_count)

            last_message = Message.query.filter_by(task_id=task.id)\
                .order_by(Message.created_at.desc()).first()

            if last_message:
                minutes_since = (datetime.utcnow() - last_message.created_at)\
                    .total_seconds() / 60
                if minutes_since < interval:
                    continue

            character = task.character
            content = generate_message(character, task)
            message = Message(content=content, task_id=task.id)
            db.session.add(message)
            db.session.commit()
            print(f"[Scheduler] '{task.name}' — message from {character.name}")