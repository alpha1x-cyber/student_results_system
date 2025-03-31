import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY') or 'secret-key-123456'
    MYSQL_HOST = os.getenv('MYSQL_HOST') or 'localhost'
    MYSQL_USER = os.getenv('MYSQL_USER') or 'root'
    MYSQL_PASSWORD = os.getenv('MYSQL_PASSWORD') or ''
    MYSQL_DB = os.getenv('MYSQL_DB') or 'student_results'
    UPLOAD_FOLDER = 'static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}
    
    @staticmethod
    def init_app(app):
        pass