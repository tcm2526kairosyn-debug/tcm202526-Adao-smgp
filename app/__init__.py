import os
from flask import Flask
from .extensions import db, login_manager
from .models import User

def create_app():
    app = Flask(__name__)

    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-only-insecure-key')
    db_url = os.environ.get('DATABASE_URL', 'postgresql://user:secret@db:5432/postgres')
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

    from flask import render_template
    _ERRORS = {
        403: ("Acesso restrito", "Não tem permissão para aceder a esta página."),
        404: ("Página não encontrada", "O endereço não existe ou o registo foi removido."),
        500: ("Erro interno", "Ocorreu um erro inesperado. Tente novamente; se persistir, contacte o administrador."),
    }

    def _error_page(code):
        heading, message = _ERRORS[code]
        if code == 500:
            db.session.rollback()
        try:
            return render_template("erro.html", code=code, heading=heading, message=message), code
        except Exception:
            return f"{code} {heading}", code

    for _code in _ERRORS:
        app.register_error_handler(_code, lambda e, c=_code: _error_page(c))

    with app.app_context():
        db.create_all()
        from .migrations import run_migrations
        run_migrations(db)
        from .seeds import run_seeds
        run_seeds()
        # gunicorn --preload: não partilhar ligações abertas no master com os workers
        db.engine.dispose()

    @app.cli.command("seed-db")
    def seed_database():
        from .seeds import run_seeds
        run_seeds()

    return app
