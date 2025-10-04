from flask import Flask, render_template, redirect, url_for, flash, abort, request
from flask_login import (
    AnonymousUserMixin,
    login_required,
    login_user,
    logout_user,
    current_user,
)
from extensions import db, login_manager, csrf
from web3_service import init_web3, get_web3
from flask_scss import Scss
from blockchain_service import append_statement, maybe_seal_block


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

    # Initialize Web3 client (if ETH_RPC_URL set)
    app.extensions = getattr(app, "extensions", {})
    app.extensions["web3"] = init_web3(app.config.get("ETH_RPC_URL", ""))

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

    # Web3 routes
    @app.route("/web3")
    def web3_status():
        w3 = get_web3()
        ok = False
        net_info = {}
        latest_block = None
        error = None
        if w3 is not None:
            try:
                ok = w3.is_connected()
                if ok:
                    net_info = {
                        "client": w3.client_version,
                    }
                    latest_block = w3.eth.block_number
            except Exception as e:  # noqa: BLE001
                error = str(e)
        return render_template(
            "web3/status.html",
            ok=ok,
            net_info=net_info,
            latest_block=latest_block,
            rpc_url=("configured" if app.config.get("ETH_RPC_URL") else "not set"),
            error=error,
        )

    @app.route("/web3/balance")
    def web3_balance():
        from flask import request as flask_request
        w3 = get_web3()
        addr = flask_request.args.get("address", "").strip()
        balance_eth = None
        error = None
        if w3 is None:
            error = "Web3 is not configured. Set ETH_RPC_URL."
        elif addr:
            try:
                checksum = w3.to_checksum_address(addr)
                wei = w3.eth.get_balance(checksum)
                balance_eth = w3.from_wei(wei, "ether")
            except Exception as e:  # noqa: BLE001
                error = str(e)
        return render_template("web3/balance.html", address=addr, balance=balance_eth, error=error)

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
            # Blockchain log: signup
            try:
                append_statement(
                    kind="signup",
                    payload={
                        "username": user.username,
                        "email": user.email,
                    },
                    user_id=user.id,
                )
                maybe_seal_block()
            except Exception:  # noqa: BLE001
                pass
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
                # Blockchain log: login
                try:
                    append_statement(
                        kind="login",
                        payload={"remember": bool(form.remember_me.data)},
                        user_id=user.id,
                    )
                    maybe_seal_block()
                except Exception:  # noqa: BLE001
                    pass
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
        uid = getattr(current_user, "id", None)
        logout_user()
        # Blockchain log: logout
        try:
            append_statement(
                kind="logout",
                payload={},
                user_id=uid,
            )
            maybe_seal_block()
        except Exception:  # noqa: BLE001
            pass
        flash("You have been logged out.", "info")
        return redirect(url_for("login"))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        from models import HelpRequest, HelpOffer

        # Stats for the current user
        total_requests = HelpRequest.query.filter_by(user_id=current_user.id).count()
        total_offers = HelpOffer.query.filter_by(helper_id=current_user.id).count()
        reputation = getattr(current_user, "reputation_score", 0.0)
        pending_tasks = HelpRequest.query.filter(
            HelpRequest.user_id == current_user.id,
            HelpRequest.status.in_(["open", "in_progress"]),
        ).count()

        # Recent activity: last 5 combined items from requests/offers
        recent_requests = (
            HelpRequest.query.filter_by(user_id=current_user.id)
            .order_by(HelpRequest.created_at.desc())
            .limit(5)
            .all()
        )
        recent_offers = (
            HelpOffer.query.filter_by(helper_id=current_user.id)
            .order_by(HelpOffer.created_at.desc())
            .limit(5)
            .all()
        )

        return render_template(
            "dashboard.html",
            stats={
                "total_requests": total_requests,
                "total_offers": total_offers,
                "reputation": reputation,
                "pending_tasks": pending_tasks,
            },
            recent={
                "requests": recent_requests,
                "offers": recent_offers,
            },
        )

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

    # Feature pages (placeholders)
    @app.route("/request-help", methods=["GET", "POST"])
    @login_required
    def request_help():
        from models import HelpRequest
        from forms import RequestHelpForm

        form = RequestHelpForm()
        if form.validate_on_submit():
            desc = form.description.data
            # Append skills and notes for now to description to avoid schema changes
            if form.skills_required.data:
                desc += f"\n\nSkills required: {form.skills_required.data}"
            if form.notes.data:
                desc += f"\n\nNotes: {form.notes.data}"

            hr = HelpRequest(
                user_id=current_user.id,
                title=form.title.data,
                description=desc,
                category=form.category.data,
                location=form.location.data or None,
                time_needed=(form.datetime_needed.data.strftime("%Y-%m-%d %H:%M") if form.datetime_needed.data else form.duration_estimate.data or None),
                price=float(form.price_offered.data) if (form.price_offered.data and not form.is_volunteer.data) else None,
                is_volunteer=bool(form.is_volunteer.data),
            )
            db.session.add(hr)
            db.session.commit()
            flash("Request posted successfully.", "success")
            return redirect(url_for("request_help"))

        # If POST with errors, flash them
        if request.method == "POST" and form.errors:
            for field, errs in form.errors.items():
                for e in errs:
                    flash(f"{field}: {e}", "error")

        # List user's existing requests
        my_requests = (
            HelpRequest.query.filter_by(user_id=current_user.id)
            .order_by(HelpRequest.created_at.desc())
            .all()
        )
        return render_template("features/request_help.html", form=form, my_requests=my_requests)

    @app.route("/offer-help")
    @login_required
    def offer_help():
        return render_template("features/offer_help.html")

    @app.route("/volunteer")
    def volunteer():
        from models import HelpRequest, HelpOffer
        from sqlalchemy import func
        from datetime import datetime, timedelta

        # Base query: volunteer-only open requests
        q = HelpRequest.query.filter(
            HelpRequest.is_volunteer.is_(True), HelpRequest.status == "open"
        )

        # Filters
        category = request.args.get("category", "").strip()
        location_q = request.args.get("location", "").strip()
        start_date = request.args.get("start_date", "").strip()
        end_date = request.args.get("end_date", "").strip()
        sort = request.args.get("sort", "newest")
        page = int(request.args.get("page", 1) or 1)
        per_page = 9

        if category:
            q = q.filter(HelpRequest.category == category)
        if location_q:
            q = q.filter(HelpRequest.location.ilike(f"%{location_q}%"))

        def parse_date(s):
            try:
                return datetime.strptime(s, "%Y-%m-%d")
            except Exception:
                return None
        sd = parse_date(start_date)
        ed = parse_date(end_date)
        if sd:
            q = q.filter(HelpRequest.created_at >= sd)
        if ed:
            q = q.filter(HelpRequest.created_at < ed + timedelta(days=1))

        # Featured urgent: oldest open volunteer requests (top 3)
        featured = (
            HelpRequest.query.filter(HelpRequest.is_volunteer.is_(True), HelpRequest.status == "open")
            .order_by(HelpRequest.created_at.asc())
            .limit(3)
            .all()
        )

        # Sorting
        if sort == "newest":
            q = q.order_by(HelpRequest.created_at.desc())
        else:
            q = q.order_by(HelpRequest.created_at.asc())

        pagination = q.paginate(page=page, per_page=per_page, error_out=False)
        items = pagination.items

        # Community impact stats (estimates)
        completed_volunteer = (
            HelpRequest.query.filter(HelpRequest.is_volunteer.is_(True), HelpRequest.status == "completed").count()
        )
        # Active volunteers = distinct helpers on accepted/completed offers for volunteer requests
        active_volunteers = (
            db.session.query(func.count(func.distinct(HelpOffer.helper_id)))
            .join(HelpRequest, HelpOffer.request_id == HelpRequest.id)
            .filter(
                HelpRequest.is_volunteer.is_(True),
                HelpOffer.status.in_(["accepted", "completed"]),
            )
            .scalar()
            or 0
        )
        people_helped = completed_volunteer
        est_hours = completed_volunteer * 2  # simple placeholder estimate

        volunteer_categories = [
            "Elderly Care",
            "Community Cleanup",
            "Teaching",
            "Food Distribution",
            "Animal Welfare",
            "Healthcare Support",
            "Other",
        ]

        return render_template(
            "features/volunteer.html",
            items=items,
            featured=featured,
            pagination=pagination,
            stats={
                "est_hours": est_hours,
                "people_helped": people_helped,
                "active_volunteers": active_volunteers,
            },
            filters={
                "category": category,
                "location": location_q,
                "start_date": start_date,
                "end_date": end_date,
                "sort": sort,
            },
            categories=volunteer_categories,
        )

    @app.route("/ngos")
    def ngos():
        from models import NGO

        q = NGO.query
        category = request.args.get("category", "").strip()
        location_q = request.args.get("location", "").strip()
        sort = request.args.get("sort", "newest")
        page = int(request.args.get("page", 1) or 1)
        per_page = 9

        if category:
            q = q.filter(NGO.category == category)
        if location_q:
            q = q.filter(NGO.location.ilike(f"%{location_q}%"))

        if sort == "newest":
            q = q.order_by(NGO.created_at.desc())
        else:
            q = q.order_by(NGO.name.asc())

        pagination = q.paginate(page=page, per_page=per_page, error_out=False)
        items = pagination.items

        categories = [
            "Education",
            "Healthcare",
            "Environment",
            "Poverty Alleviation",
            "Animal Welfare",
            "Women & Children",
            "Disaster Relief",
            "Other",
        ]

        return render_template(
            "features/ngos.html",
            items=items,
            pagination=pagination,
            categories=categories,
            filters={
                "category": category,
                "location": location_q,
                "sort": sort,
            },
        )

    @app.route("/ngos/<int:ngo_id>")
    def ngo_detail(ngo_id: int):
        from models import NGO
        ngo = NGO.query.get_or_404(ngo_id)
        # Placeholder campaigns/needs
        campaigns = [
            {"title": "Monthly Food Drive", "need": "Volunteers for distribution"},
            {"title": "School Supplies", "need": "Donations of notebooks and pens"},
        ]
        return render_template("features/ngo_detail.html", ngo=ngo, campaigns=campaigns)

    @app.route("/ngos/submit", methods=["GET", "POST"])
    @login_required
    def ngo_submit():
        from models import NGO
        from forms import NGOForm

        form = NGOForm()
        if form.validate_on_submit():
            ngo = NGO(
                name=form.name.data,
                description=form.description.data,
                category=form.category.data or None,
                location=form.location.data or None,
                contact_email=form.contact_email.data or None,
                website=form.website.data or None,
                verified_status=False,
            )
            db.session.add(ngo)
            db.session.commit()
            flash("NGO submitted for approval. Our team will verify and publish it.", "success")
            return redirect(url_for("ngos"))

        if request.method == "POST" and form.errors:
            for field, errs in form.errors.items():
                for e in errs:
                    flash(f"{field}: {e}", "error")

        return render_template("features/ngo_submit.html", form=form)

    @app.route("/nearby")
    @login_required
    def nearby():
        return render_template("features/nearby.html")

    @app.route("/marketplace")
    def marketplace():
        from models import HelpRequest, User
        from sqlalchemy import or_, and_

        q = HelpRequest.query.filter(HelpRequest.status == "open")

        # Filters
        category = request.args.get("category", "").strip()
        location_q = request.args.get("location", "").strip()
        min_price = request.args.get("min_price", "").strip()
        max_price = request.args.get("max_price", "").strip()
        include_volunteer = request.args.get("include_volunteer", "on")  # default include
        start_date = request.args.get("start_date", "").strip()  # YYYY-MM-DD
        end_date = request.args.get("end_date", "").strip()      # YYYY-MM-DD
        sort = request.args.get("sort", "newest")
        page = int(request.args.get("page", 1) or 1)
        per_page = 9

        if category:
            q = q.filter(HelpRequest.category == category)
        if location_q:
            q = q.filter(HelpRequest.location.ilike(f"%{location_q}%"))

        # Price / volunteer
        price_filters = []
        if min_price:
            try:
                price_filters.append(HelpRequest.price >= float(min_price))
            except ValueError:
                pass
        if max_price:
            try:
                price_filters.append(HelpRequest.price <= float(max_price))
            except ValueError:
                pass
        if price_filters:
            range_filter = and_(*price_filters)
            if include_volunteer:
                q = q.filter(or_(HelpRequest.is_volunteer.is_(True), range_filter))
            else:
                q = q.filter(range_filter, HelpRequest.is_volunteer.is_(False))
        else:
            if not include_volunteer:
                q = q.filter(HelpRequest.is_volunteer.is_(False))

        # Date range (use created_at since time_needed is free text)
        from datetime import datetime
        def parse_date(s):
            try:
                return datetime.strptime(s, "%Y-%m-%d")
            except Exception:
                return None
        sd = parse_date(start_date)
        ed = parse_date(end_date)
        if sd:
            q = q.filter(HelpRequest.created_at >= sd)
        if ed:
            from datetime import timedelta
            q = q.filter(HelpRequest.created_at < ed + timedelta(days=1))

        # Sorting
        if sort == "price_high_low":
            q = q.order_by(HelpRequest.price.desc().nullslast(), HelpRequest.created_at.desc())
        elif sort == "price_low_high":
            q = q.order_by(HelpRequest.price.asc().nullsfirst(), HelpRequest.created_at.desc())
        elif sort == "urgent":
            q = q.order_by(HelpRequest.created_at.asc())
        else:  # newest
            q = q.order_by(HelpRequest.created_at.desc())

        pagination = q.paginate(page=page, per_page=per_page, error_out=False)
        items = pagination.items

        categories = ["Cooking", "Cleaning", "Moving", "Tutoring", "Errands", "Technical", "Other"]

        return render_template(
            "features/marketplace.html",
            items=items,
            pagination=pagination,
            categories=categories,
            filters={
                "category": category,
                "location": location_q,
                "min_price": min_price,
                "max_price": max_price,
                "include_volunteer": include_volunteer,
                "start_date": start_date,
                "end_date": end_date,
                "sort": sort,
            },
        )

    @app.route("/requests/<int:request_id>", methods=["GET", "POST"])
    @login_required
    def request_detail(request_id: int):
        from models import HelpRequest, User, HelpOffer
        from forms import OfferHelpForm

        req = HelpRequest.query.get_or_404(request_id)
        requester = User.query.get(req.user_id)

        form = OfferHelpForm()
        if form.validate_on_submit():
            msg = form.message.data
            if form.availability.data:
                msg += "\n\nAvailability: Can start."
            if form.timeframe.data:
                msg += f"\n\nTimeframe: {form.timeframe.data}"
            offer = HelpOffer(
                request_id=req.id,
                helper_id=current_user.id,
                message=msg,
                status="pending",
            )
            db.session.add(offer)
            db.session.commit()
            flash("Offer submitted to the requester.", "success")
            return redirect(url_for("request_detail", request_id=req.id))

        if request.method == "POST" and form.errors:
            for field, errs in form.errors.items():
                for e in errs:
                    flash(f"{field}: {e}", "error")

        # Existing offers by current user for this request
        my_offer = None
        if current_user.is_authenticated:
            my_offer = (
                HelpOffer.query.filter_by(request_id=req.id, helper_id=current_user.id)
                .order_by(HelpOffer.created_at.desc())
                .first()
            )

        return render_template("features/request_detail.html", req=req, requester=requester, form=form, my_offer=my_offer)

    @app.route("/my-offers")
    @login_required
    def my_offers():
        from models import HelpOffer, HelpRequest

        offers = (
            HelpOffer.query.filter_by(helper_id=current_user.id)
            .order_by(HelpOffer.created_at.desc())
            .all()
        )
        grouped = {
            "pending": [o for o in offers if o.status == "pending"],
            "accepted": [o for o in offers if o.status == "accepted"],
            "rejected": [o for o in offers if o.status == "rejected"],
            "completed": [o for o in offers if o.status == "completed"],
        }
        badge_counts = {k: len(v) for k, v in grouped.items()}
        return render_template("features/my_offers.html", grouped=grouped, badge_counts=badge_counts)

    # Profiles
    @app.route("/u/<string:username>")
    def profile_view(username: str):
        from models import User, HelpRequest, HelpOffer, Review
        user = User.query.filter_by(username=username).first_or_404()

        # Stats
        requests_completed = HelpRequest.query.filter_by(user_id=user.id, status="completed").count()
        helps_completed = HelpOffer.query.filter_by(helper_id=user.id, status="completed").count()

        # Success rate: completed offers / all offers (accepted or completed considered attempts)
        total_offers_attempted = HelpOffer.query.filter(HelpOffer.helper_id == user.id, HelpOffer.status.in_(["accepted", "completed", "rejected"]))
        total_offers_attempted_count = total_offers_attempted.count() or 0
        success_rate = 0
        if total_offers_attempted_count:
            success_rate = int((helps_completed / total_offers_attempted_count) * 100)

        # Reputation tier (simple mapping)
        score = float(getattr(user, "reputation_score", 0.0) or 0.0)
        if score >= 80:
            tier = "Expert"
        elif score >= 50:
            tier = "Trusted"
        elif score >= 20:
            tier = "Helper"
        else:
            tier = "Beginner"

        # Reviews received (paginated)
        page = int(request.args.get("page", 1) or 1)
        per_page = 5
        reviews_q = Review.query.filter_by(reviewee_id=user.id).order_by(Review.created_at.desc())
        reviews = reviews_q.paginate(page=page, per_page=per_page, error_out=False)

        return render_template(
            "profile/view.html",
            profile_user=user,
            stats={
                "requests_completed": requests_completed,
                "helps_completed": helps_completed,
                "success_rate": success_rate,
            },
            tier=tier,
            reviews=reviews,
        )

    @app.route("/settings/profile", methods=["GET", "POST"])
    @login_required
    def profile_edit():
        from models import User
        from forms import ProfileForm

        user = current_user
        form = ProfileForm(obj=user)
        if form.validate_on_submit():
            user.full_name = form.full_name.data or None
            user.phone = form.phone.data or None
            user.location = form.location.data or None
            user.bio = form.bio.data or None
            user.skills = form.skills.data or None
            user.avatar_url = form.avatar_url.data or None
            db.session.commit()
            flash("Profile updated.", "success")
            return redirect(url_for("profile_view", username=user.username))

        if request.method == "POST" and form.errors:
            for field, errs in form.errors.items():
                for e in errs:
                    flash(f"{field}: {e}", "error")

        return render_template("profile/edit.html", form=form)

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
