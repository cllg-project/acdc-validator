import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me-in-production")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'annotations.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DATA_PATH = os.environ.get(
        "DATA_PATH", os.path.join(BASE_DIR, "book-samples")
    )
