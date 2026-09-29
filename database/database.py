"""
Single shared SQLAlchemy instance. Imported by app.py and every
model/route/service module so there is exactly one database
connection pool for the whole application.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
