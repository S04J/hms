import os
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, 'instance', 'hms.db')
os.makedirs(os.path.join(BASE_DIR, 'instance'), exist_ok=True)


class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'hms-secret-key-2024-change-in-production')
    
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL', f'sqlite:///{DB_PATH}'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'check_same_thread': False},
        'pool_pre_ping': True,
    }

    JWT_SECRET_KEY = os.environ.get('JWT_SECRET_KEY', 'jwt-secret-key-2024')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=24)

    CACHE_TYPE = 'RedisCache'
    CACHE_REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    CACHE_REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    CACHE_REDIS_DB = 0
    CACHE_DEFAULT_TIMEOUT = 300

    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', 'redis://localhost:6379/1')
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = 587
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'hms@hospital.com')

    GCHAT_WEBHOOK_URL = os.environ.get('GCHAT_WEBHOOK_URL', '')

    ADMIN_USERNAME = 'admin'
    ADMIN_PASSWORD = 'admin123'
    ADMIN_EMAIL = 'admin@hospital.com'


class DevelopmentConfig(Config):
    DEBUG = True
    CACHE_TYPE = 'SimpleCache'


config = {
    'development': DevelopmentConfig,
    'default': DevelopmentConfig,
}
