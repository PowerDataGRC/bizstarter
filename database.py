import json
import os
from extensions import db
from models import AssessmentMessage

ASSESSMENT_MESSAGES_JSON_PATH = 'assessment_messages.json' # Path to the original JSON

def init_db(app):
    """
    Initializes the database by creating tables and seeding initial data
    from the assessment_messages.json file if the table is empty.
    This now uses SQLAlchemy to be database-agnostic.
    """
    with app.app_context():
        # Check if the table is empty before seeding
        if not AssessmentMessage.query.first():
            print(f"Seeding assessment_messages table from {ASSESSMENT_MESSAGES_JSON_PATH}...")
            try:
                with open(ASSESSMENT_MESSAGES_JSON_PATH, 'r') as f:
                    json_data = json.load(f)
                
                for risk_level, data in json_data.items():
                    message = AssessmentMessage(
                        risk_level=risk_level,
                        status=data['status'],
                        caption=data['caption'],
                        status_class=data['status_class'],
                        dscr_status=data['dscr_status']
                    )
                    db.session.add(message)
                db.session.commit()
                print("Assessment messages seeded successfully.")
            except FileNotFoundError:
                print(f"Warning: {ASSESSMENT_MESSAGES_JSON_PATH} not found. Assessment messages table might be empty.")
            except Exception as e:
                print(f"Error seeding assessment messages: {e}")
                db.session.rollback()

def get_assessment_messages():
    """Retrieves all assessment messages from the database using SQLAlchemy."""
    messages = {}
    rows = AssessmentMessage.query.all()
    for row in rows:
        messages[row.risk_level] = {
            'status': row.status,
            'caption': row.caption,
            'status_class': row.status_class,
            'dscr_status': row.dscr_status
        }
    return messages