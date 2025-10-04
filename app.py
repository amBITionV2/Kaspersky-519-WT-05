from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_login import (
    AnonymousUserMixin,
    login_required,
    login_user,
    logout_user,
    current_user,
)
from extensions import db, login_manager, csrf
from flask_scss import Scss


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object("config.Config")
    # SCSS configuration
    app.config.setdefault("SCSS_ASSET_DIR", "assets/scss")
    app.config.setdefault("STATIC_ASSET_DIR", "static/css")

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    # Initialize SCSS compiler
    Scss(app, static_dir=app.config["STATIC_ASSET_DIR"], asset_dir=app.config["SCSS_ASSET_DIR"])

    # Flask-Login config
    class _AnonymousUser(AnonymousUserMixin):
        pass

    login_manager.anonymous_user = _AnonymousUser
    login_manager.login_view = "login"

    @login_manager.user_loader
    def load_user(user_id):  # noqa: ANN001
        # Lazy import to avoid circular imports
        from models import User
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # Auto-create tables on first run
    with app.app_context():
        # Import models so SQLAlchemy is aware before create_all
        import models  # noqa: F401
        db.create_all()

    # Basic index route
    @app.route("/")
    @login_required
    def index():
        return render_template("index.html")

    @app.route("/about")
    def about():
        return render_template("about.html")

    # Auth routes
    @app.route("/signup", methods=["GET", "POST"])
    def signup():
        from models import User
        from forms import SignUpForm

        form = SignUpForm()
        if form.validate_on_submit():
            # Check existing user by email/username
            existing_email = User.query.filter_by(email=form.email.data.lower()).first()
            existing_user = User.query.filter_by(username=form.username.data).first()
            if existing_email:
                flash("Email already registered.", "error")
                return render_template("auth/signup.html", form=form)
            if existing_user:
                flash("Username already taken.", "error")
                return render_template("auth/signup.html", form=form)

            user = User(
                username=form.username.data,
                email=form.email.data.lower(),
                full_name=form.full_name.data or None,
                phone=form.phone.data or None,
                location=form.location.data or None,
            )
            user.set_password(form.password.data)
            db.session.add(user)
            db.session.commit()
            flash("Account created. Please log in.", "success")
            return redirect(url_for("login"))

        # If POST with errors, surface them
        if request.method == "POST" and form.errors:
            for field, errs in form.errors.items():
                for e in errs:
                    flash(f"{field}: {e}", "error")
        return render_template("auth/signup.html", form=form)

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if current_user.is_authenticated:
            return redirect(url_for("post_login_redirect"))

        from models import User
        from forms import LoginForm

        form = LoginForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data.lower()).first()
            if user and user.check_password(form.password.data):
                login_user(user, remember=form.remember_me.data)
                flash("Logged in successfully.", "success")
                return redirect(url_for("post_login_redirect"))
            flash("Invalid email or password.", "error")
        # If POST with errors, surface them
        if request.method == "POST" and form.errors:
            for field, errs in form.errors.items():
                for e in errs:
                    flash(f"{field}: {e}", "error")
        return render_template("auth/login.html", form=form)

    @app.route("/logout")
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        return render_template("dashboard.html")

    @app.route("/admin")
    @login_required
    def admin():
        if getattr(current_user, "user_type", "user") != "admin":
            flash("Admin access required.", "error")
            return redirect(url_for("dashboard"))
        return render_template("admin.html")

    @app.route("/post-login-redirect")
    @login_required
    def post_login_redirect():
        if getattr(current_user, "user_type", "user") == "admin":
            return redirect(url_for("admin"))
        return redirect(url_for("dashboard"))

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
