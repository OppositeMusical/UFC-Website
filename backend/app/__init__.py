from __future__ import annotations

from flask import Flask

from app.config import Config
from app.extensions import Session, init_engine
from app.services.db.session import init_db
from app.utils.paths import resource_path


def create_app(config_class: type[Config] = Config) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(resource_path("templates")),
        static_folder=str(resource_path("static")),
    )
    app.config.from_object(config_class)

    if not app.testing:
        # Must run before init_engine()/init_db() ever create the sqlite
        # file - see app/utils/seed.py for why. Skipped under TestConfig so
        # unit tests stay fast and isolated from real bundled fighter data.
        from app.utils.seed import maybe_seed_data_dir

        maybe_seed_data_dir()

    init_engine(config_class.SQLALCHEMY_DATABASE_URI())
    init_db()

    from app.blueprints.betting.routes import bp as betting_bp
    from app.blueprints.chat.routes import bp as chat_bp
    from app.blueprints.fighters.routes import bp as fighters_bp
    from app.blueprints.main.routes import bp as main_bp
    from app.blueprints.settings.routes import bp as settings_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(betting_bp)
    app.register_blueprint(fighters_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(chat_bp)

    @app.teardown_appcontext
    def remove_session(exception=None):
        Session.remove()

    return app
