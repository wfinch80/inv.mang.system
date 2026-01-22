from app import app, db, AdminUser
from werkzeug.security import generate_password_hash

# This block ensures we are talking to the correct database
with app.app_context():
    # 1. Force creation of all tables
    db.create_all()
    print("--- Database Tables Created ---")

    # 2. Add the user
    # We check if it exists first to avoid duplicates
    if not AdminUser.query.filter_by(username="1605").first():
        new_user = AdminUser(
            username="1605",
            password_hash=generate_password_hash("Un!corn1980")
        )
        db.session.add(new_user)
        db.session.commit()
        print("--- User '1605' Created Successfully ---")
    else:
        print("--- User '1605' Already Exists ---")