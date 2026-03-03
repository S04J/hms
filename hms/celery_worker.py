
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from backend.tasks import make_celery, register_tasks

flask_app = create_app()
celery = make_celery(flask_app)
register_tasks(celery, flask_app)


from celery.schedules import crontab

celery.conf.beat_schedule = {
    'daily-reminders': {
        'task': 'tasks.send_daily_reminders',
        'schedule': crontab(hour=8, minute=0),  
    },
    'monthly-report': {
        'task': 'tasks.send_monthly_report',
        'schedule': crontab(day_of_month=1, hour=7, minute=0),  
    },
}
celery.conf.timezone = 'Asia/Kolkata'
