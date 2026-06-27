from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"


def create_app(config=None):
    app = Flask(__name__)
    app.config.from_object("config.Config")
    if config:
        app.config.update(config)

    db.init_app(app)
    login_manager.init_app(app)

    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from .routes.auth import bp as auth_bp
    from .routes.validate import bp as validate_bp
    from .routes.review import bp as review_bp
    from .routes.image import bp as image_bp
    from .routes.stats import bp as stats_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(validate_bp)
    app.register_blueprint(review_bp)
    app.register_blueprint(image_bp)
    app.register_blueprint(stats_bp)

    from . import cli
    cli.register(app)

    return app
