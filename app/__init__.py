import os
from flask import Flask
from .extensions import db, login_manager
from .models import User

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-insecure-key')
    db_url = os.environ.get('DATABASE_URL', 'postgresql://user:secret@db:5432/postgres')
    # Railway uses 'postgres://' prefix — SQLAlchemy requires 'postgresql://'
    if db_url.startswith('postgres://'):
        db_url = db_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = db_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    app.config['RESEND_API_KEY'] = os.environ.get('RESEND_API_KEY', '')
    app.config['RESEND_FROM']   = os.environ.get('RESEND_FROM', 'KairoSyn SAD <onboarding@resend.dev>')
    app.config['ADMIN_EMAIL']   = os.environ.get('ADMIN_EMAIL', '')
    app.config['BASE_URL']      = os.environ.get('FLASK_BASE_URL', 'http://127.0.0.1:5000')

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'main.login'

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .routes import main
    app.register_blueprint(main)

    with app.app_context():
        db.create_all()
        from .migrations import run_migrations
        run_migrations(db)
        from .seeds import run_seeds
        run_seeds()

    @app.cli.command("seed-db")
    def seed_database():
        from .seeds import run_seeds
        run_seeds()

    return app
