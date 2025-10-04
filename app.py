from flask import Flask, render_template
from flask_login import AnonymousUserMixin
from extensions import db, login_manager, csrf


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object("config.Config")

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    # Minimal Flask-Login config: define anonymous user and a no-op loader
    class _AnonymousUser(AnonymousUserMixin):
        pass

    login_manager.anonymous_user = _AnonymousUser

    @login_manager.user_loader
    def load_user(user_id):  # noqa: ANN001
        # Return None to indicate no authenticated user yet
        return None

    # Auto-create tables on first run
    with app.app_context():
        # Import models so SQLAlchemy is aware before create_all
        import models  # noqa: F401
        db.create_all()

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
