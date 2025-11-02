from api import app, db

with app.app_context():
    db.create_all()

#this will create the db