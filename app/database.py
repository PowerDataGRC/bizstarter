import json
import os
from .extensions import db
from .models import AssessmentMessage

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