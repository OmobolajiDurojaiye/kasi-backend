from app import create_app
from app.extensions import db
from app.modules.auth.models import User

app = create_app()

def promote_to_admin(email):
    with app.app_context():
        user = User.query.filter_by(email=email).first()
        if not user:
            print(f"User with email {email} not found.")
            return

        user.is_admin = True
        user.admin_role = 'Super Admin'
        db.session.commit()
        print(f"Success! User {email} has been promoted to Super Admin.")

if __name__ == "__main__":
    email_to_promote = input("Enter the email of the user to promote to admin: ")
    promote_to_admin(email_to_promote.strip())
