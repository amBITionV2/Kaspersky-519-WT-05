from flask import Flask, render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, AnonymousUserMixin
from flask_wtf.csrf import CSRFProtect

# Global extensions
_db = SQLAlchemy()
_login_manager = LoginManager()
_csrf = CSRFProtect()


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object("config.Config")

    # Init extensions
    _db.init_app(app)
    _login_manager.init_app(app)
    _csrf.init_app(app)

    # Minimal Flask-Login config: define anonymous user and a no-op loader
    class _AnonymousUser(AnonymousUserMixin):
        pass

    _login_manager.anonymous_user = _AnonymousUser

    @_login_manager.user_loader
    def load_user(user_id):  # noqa: ANN001
        # Return None to indicate no authenticated user yet
        return None

    # Basic index route
    @app.route("/")
    def index():
        return render_template("index.html")

    # Error handlers
    @app.errorhandler(404)
    def not_found_error(error):  # noqa: ANN001
        return render_template("errors/404.html"), 404

    @app.errorhandler(500)
    def internal_error(error):  # noqa: ANN001
        return render_template("errors/500.html"), 500

    return app


# Optional: allow `python app.py` to run a dev server
if __name__ == "__main__":
    application = create_app()
    application.run(host="127.0.0.1", port=5000, debug=True)
