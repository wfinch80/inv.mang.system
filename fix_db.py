import sys
import os
from app import app, db, AdminUser
from werkzeug.security import generate_password_hash

print("--- Starting Database Fix ---")

# 1. Force the app to wake up so we can talk to the database
with app.app_context():

    # 2. Create the missing tables (This fixes the "no such table" error)
    db.create_all()
    print("SUCCESS: Database tables created.")

    # 3. Create your user
    # We check if '1605' exists first so we don't create duplicates
    user = AdminUser.query.filter_by(username="1605").first()

    if not user:
        new_user = AdminUser(
            username="1605",
            password_hash=generate_password_hash("Un!corn1980")
        )
        db.session.add(new_user)
        db.session.commit()
        print("SUCCESS: User '1605' created with password 'Un!corn1980'")
    else:
        print("INFO: User '1605' already exists. Skipping creation.")

print("--- Fix Complete ---")
