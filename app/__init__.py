from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix

db = SQLAlchemy()
migrate = Migrate()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object("config.Config")
    if config:
        app.config.update(config)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)

    # Honour X-Forwarded-Prefix / SCRIPT_NAME set by nginx for subpath deployments
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_prefix=1)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .routes.auth import bp as auth_bp
    from .routes.home import bp as home_bp
    from .routes.validate import bp as validate_bp
    from .routes.review import bp as review_bp
    from .routes.image import bp as image_bp
    from .routes.stats import bp as stats_bp
    from .routes.validated import bp as validated_bp
    from .routes.disagreements import bp as disagreements_bp
    from .routes.export import bp as export_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(home_bp)
    app.register_blueprint(validate_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(image_bp)
    app.register_blueprint(stats_bp)
    app.register_blueprint(validated_bp)
    app.register_blueprint(disagreements_bp)
    app.register_blueprint(export_bp)

    from . import cli
    cli.register(app)

    return app
