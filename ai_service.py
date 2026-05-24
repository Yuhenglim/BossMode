import anthropic
from datetime import datetime
import os

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

def check_deadline(task):
    today = datetime.today().date()
    deadline = datetime.strptime(task.deadline, "%Y-%m-%d").date()
    days_left = (deadline - today).days

    if days_left > 3:
        urgency = "casual reminder"
    elif days_left == 3:
        urgency = "getting a bit urgent"
    elif days_left == 2:
        urgency = "pressure building"
    elif days_left == 1:
        urgency = "very urgent"
    else:
        urgency = "extremely angry, the deadline has passed"

    return urgency

def generate_message(character, task):
    urgency = check_deadline(task)

    prompt = f"""
    You are {character.name}, a {character.role}.
    Your personality is: {character.personality}.
    Urgency level: {urgency}

    You need to message your employee about this task:
    - Task: {task.name}
    - Description: {task.description}
    - Deadline: {task.deadline}
    - Completed: {task.is_complete}

    Write a short chat message (1-3 sentences) to push them to complete it.
    Stay in character based on your personality and the urgency level.
    """

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text