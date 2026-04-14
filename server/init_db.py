from flask_migrate import upgrade

from . import create_app


def main():
    app = create_app()
    with app.app_context():
        upgrade()
        print("Database migrations applied successfully.")


if __name__ == "__main__":
    main()
