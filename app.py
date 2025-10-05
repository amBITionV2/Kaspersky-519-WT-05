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
import logging
from flask_scss import Scss
from blockchain_service import append_statement, maybe_seal_block


def create_app() -> Flask:
    """Application factory."""
    app = Flask(__name__, static_folder="static", template_folder="templates")
    # Optional: load .env if present
    try:
        from dotenv import load_dotenv  # type: ignore
        load_dotenv()
    except Exception:
        pass
    app.config.from_object("config.Config")
    # Logging setup
    level = getattr(logging, str(app.config.get("LOG_LEVEL", "INFO")).upper(), logging.INFO)
    logging.basicConfig(level=level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("werkzeug").setLevel(level)
    # SCSS configuration
    app.config.setdefault("SCSS_ASSET_DIR", "assets/scss")

    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    # Initialize Web3 client (if ETH_RPC_URL set)
    app.extensions = getattr(app, "extensions", {})
    app.extensions["web3"] = init_web3(app.config.get("ETH_RPC_URL", ""))

    # Blockchain HTTP request logging
    @app.before_request
    def log_http_request():
        # Skip logging for static files and certain endpoints
        if (request.endpoint in ['static'] or
            request.path.startswith('/static/') or
            request.endpoint in ['web3_status', 'web3_balance'] or
            request.method in ['OPTIONS', 'HEAD']):
            return

        user_id = getattr(current_user, 'id', None) if current_user.is_authenticated else None

        try:
            append_statement(
                kind="http_request",
                payload={
                    "method": request.method,
                    "path": request.path,
                    "query_string": request.query_string.decode('utf-8') if request.query_string else "",
                    "user_agent": request.headers.get('User-Agent', '')[:200],  # Limit length
                    "remote_addr": request.remote_addr,
                    "referrer": request.headers.get('Referer', '')[:200],  # Limit length
                },
                user_id=user_id,
            )
            maybe_seal_block()
        except Exception:  # noqa: BLE001
            # Silently fail to not break the request flow
            pass

    # Flask-Login config
    class _AnonymousUser(AnonymousUserMixin):
        pass

    login_manager.anonymous_user = _AnonymousUser
    login_manager.login_view = "login"

    # ------------------
    # Admin utilities
    # ------------------
    from functools import wraps

    def admin_required(view_func):
        @wraps(view_func)
        def _wrapped(*args, **kwargs):
            if not current_user.is_authenticated or getattr(current_user, "user_type", "user") != "admin":
                flash("Admin access required.", "error")
                return redirect(url_for("dashboard"))
            return view_func(*args, **kwargs)
        return _wrapped

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
    @app.route("/connect-wallet")
    def connect_wallet():
        return render_template("wallet/connect.html")
    @app.route("/blockchain/blocks")
    @login_required
    def blockchain_blocks():
        from models import Block, Statement

        # Get pagination parameters
        page = int(request.args.get("page", 1) or 1)
        per_page = 10

        # Query blocks with statements count
        blocks_query = db.session.query(
            Block,
            db.func.count(Statement.id).label('statement_count')
        ).outerjoin(Statement, Block.id == Statement.block_id)\
         .group_by(Block.id)\
         .order_by(Block.index.desc())

        pagination = blocks_query.paginate(page=page, per_page=per_page, error_out=False)
        blocks_with_counts = pagination.items

        # Get total blocks count
        total_blocks = db.session.query(Block).count()

        return render_template(
            "blockchain/blocks.html",
            blocks_with_counts=blocks_with_counts,
            pagination=pagination,
            total_blocks=total_blocks,
        )
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

    

    @app.route("/post-login-redirect")
    @login_required
    def post_login_redirect():
        # Check for specific admin credentials
        if (getattr(current_user, "username", "") == "admin" and
            getattr(current_user, "email", "") == "admin@dailyhelper.com"):
            return redirect(url_for("blockchain_blocks"))
        return redirect(url_for("dashboard"))

    # Feature pages (placeholders)
    @app.route("/request-help", methods=["GET", "POST"])
    @login_required
    def request_help():
        from models import HelpRequest
        from forms import RequestHelpForm

        if getattr(current_user, "is_blacklisted", False):
            flash("Your account is blacklisted. You cannot create requests.", "error")
            return redirect(url_for("dashboard"))

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

            # Blockchain log: request creation
            try:
                append_statement(
                    kind="request_create",
                    payload={
                        "request_id": hr.id,
                        "title": hr.title,
                        "category": hr.category,
                        "is_volunteer": hr.is_volunteer,
                        "price": float(hr.price) if hr.price else None,
                    },
                    user_id=current_user.id,
                )
                maybe_seal_block()
            except Exception:  # noqa: BLE001
                pass

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

            # Blockchain log: NGO submission
            try:
                append_statement(
                    kind="ngo_submit",
                    payload={
                        "ngo_id": ngo.id,
                        "name": ngo.name,
                        "category": ngo.category,
                        "location": ngo.location,
                    },
                    user_id=current_user.id,
                )
                maybe_seal_block()
            except Exception:  # noqa: BLE001
                pass

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
        from models import User
        import math

        # Require current user location
        if current_user.latitude is None or current_user.longitude is None:
            flash("Set your location (latitude/longitude) in your profile to see nearby people.", "info")
            return redirect(url_for("profile_edit"))

        # Filters
        try:
            radius_km = float(request.args.get("radius", 5))
        except Exception:
            radius_km = 5.0
        skill_q = (request.args.get("skills", "").strip() or None)
        try:
            rep_min = float(request.args.get("rep_min", 0))
        except Exception:
            rep_min = 0.0

        candidates = (
            User.query.filter(
                User.id != current_user.id,
                User.latitude.isnot(None),
                User.longitude.isnot(None),
                User.is_blacklisted.is_(False),
                (User.reputation_score >= rep_min),
            ).all()
        )

        def haversine(lat1, lon1, lat2, lon2):
            R = 6371.0
            phi1 = math.radians(lat1)
            phi2 = math.radians(lat2)
            dphi = math.radians(lat2 - lat1)
            dlambda = math.radians(lon2 - lon1)
            a = math.sin(dphi/2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda/2) ** 2
            c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
            return R * c

        results = []
        for u in candidates:
            dist = haversine(current_user.latitude, current_user.longitude, float(u.latitude), float(u.longitude))
            if dist <= radius_km:
                if skill_q:
                    if not (u.skills and skill_q.lower() in u.skills.lower()):
                        continue
                results.append({
                    "user": u,
                    "distance": round(dist, 2),
                })
        results.sort(key=lambda x: (x["distance"], -(x["user"].reputation_score or 0)))

        filters = {
            "radius": radius_km,
            "skills": skill_q or "",
            "rep_min": rep_min,
        }

        return render_template("features/nearby.html", results=results, filters=filters)

    # Static pages
    @app.route("/help")
    def help_page():
        return render_template("help.html")

    @app.route("/terms")
    def terms_page():
        return render_template("terms.html")

    @app.route("/privacy")
    def privacy_page():
        return render_template("privacy.html")

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
        from models import HelpRequest, User, HelpOffer, Review
        from forms import OfferHelpForm, ReviewForm, AcceptOfferForm, CompleteTaskForm

        req = HelpRequest.query.get_or_404(request_id)
        requester = User.query.get(req.user_id)

        offer_form = OfferHelpForm()
        review_form = ReviewForm()
        accept_form = AcceptOfferForm()
        complete_form = CompleteTaskForm()

        # Get all offers for this request
        all_offers = HelpOffer.query.filter_by(request_id=request_id).order_by(HelpOffer.created_at.desc()).all()

        # Check if current user is the requester
        is_requester = current_user.id == req.user_id

        # Handle offer submit
        if getattr(current_user, "is_blacklisted", False) and offer_form.submit.data:
            flash("Your account is blacklisted. You cannot submit offers.", "error")
            return redirect(url_for("request_detail", request_id=req.id))
        if offer_form.submit.data and offer_form.validate_on_submit():
            msg = offer_form.message.data
            if offer_form.availability.data:
                msg += "\n\nAvailability: Can start."
            if offer_form.timeframe.data:
                msg += f"\n\nTimeframe: {offer_form.timeframe.data}"
            offer = HelpOffer(
                request_id=req.id,
                helper_id=current_user.id,
                message=msg,
                status="pending",
            )
            db.session.add(offer)
            db.session.commit()

            # Blockchain log: offer submission
            try:
                append_statement(
                    kind="offer_submit",
                    payload={
                        "request_id": req.id,
                        "offer_id": offer.id,
                        "message_length": len(offer.message or ""),
                    },
                    user_id=current_user.id,
                )
                maybe_seal_block()
            except Exception:  # noqa: BLE001
                pass

            flash("Offer submitted to the requester.", "success")
            return redirect(url_for("request_detail", request_id=req.id))

        # Handle offer acceptance (only by requester)
        if is_requester and accept_form.submit.data:
            offer_id = request.form.get('offer_id')
            if offer_id:
                offer = HelpOffer.query.get_or_404(offer_id)
                if offer.request_id == req.id and offer.status == "pending":
                    # Reject all other offers
                    HelpOffer.query.filter_by(request_id=req.id, status="pending").update({"status": "rejected"})

                    # Accept the selected offer
                    offer.status = "accepted"
                    req.status = "in_progress"
                    db.session.commit()

                    # Blockchain log: offer acceptance
                    try:
                        append_statement(
                            kind="offer_accepted",
                            payload={
                                "request_id": req.id,
                                "offer_id": offer.id,
                                "helper_id": offer.helper_id,
                                "requester_id": current_user.id,
                            },
                            user_id=current_user.id,
                        )
                        maybe_seal_block()
                    except Exception:  # noqa: BLE001
                        pass

                    flash(f"Offer from {offer.helper.full_name or offer.helper.username} has been accepted!", "success")
                    return redirect(url_for("request_detail", request_id=req.id))

        # Handle task completion (only by requester)
        if is_requester and complete_form.submit.data and req.status == "in_progress":
            accepted_offer = HelpOffer.query.filter_by(request_id=req.id, status="accepted").first()
            if accepted_offer:
                req.status = "completed"
                accepted_offer.status = "completed"
                db.session.commit()

                # Blockchain log: task completion
                try:
                    append_statement(
                        kind="task_completed",
                        payload={
                            "request_id": req.id,
                            "helper_id": accepted_offer.helper_id,
                            "requester_id": current_user.id,
                        },
                        user_id=current_user.id,
                    )
                    maybe_seal_block()
                except Exception:  # noqa: BLE001
                    pass

                flash("Task marked as completed! You can now leave a review.", "success")
                return redirect(url_for("request_detail", request_id=req.id))

        # Handle review submit (only for completed tasks and participants)
        if review_form.submit.data and review_form.validate_on_submit():
            # Only allow reviews when a completed offer exists for this request
            completed = (
                HelpOffer.query.filter_by(request_id=req.id, status="completed").first()
            )
            if not completed or req.status != "completed":
                flash("Reviews are only allowed for completed tasks.", "error")
                return redirect(url_for("request_detail", request_id=req.id))

            # Determine counterpart
            if current_user.id == req.user_id:
                reviewee_id = completed.helper_id
            elif current_user.id == completed.helper_id:
                reviewee_id = req.user_id
            else:
                flash("You are not a participant in this task.", "error")
                return redirect(url_for("request_detail", request_id=req.id))

            # Prevent duplicate per task per reviewer
            exists = (
                Review.query.filter_by(request_id=req.id, reviewer_id=current_user.id).first()
            )
            if exists:
                flash("You have already reviewed this task.", "error")
                return redirect(url_for("request_detail", request_id=req.id))

            rating = int(review_form.rating.data)
            comment = (review_form.comment.data or "").strip()
            rv = Review(
                request_id=req.id,
                reviewer_id=current_user.id,
                reviewee_id=reviewee_id,
                rating=rating,
                comment=comment or None,
            )
            db.session.add(rv)

            # Simple reputation update for the reviewee
            reviewee = User.query.get(reviewee_id)
            delta = 0
            if reviewee is not None:
                delta = rating * 3
                if rating == 5:
                    delta += 2
                if rating <= 2:
                    delta -= 5
                new_score = max(0.0, min(100.0, float(reviewee.reputation_score or 0.0) + delta))
                reviewee.reputation_score = new_score

            # Blockchain log: review submission
            try:
                append_statement(
                    kind="review_submit",
                    payload={
                        "request_id": req.id,
                        "review_id": rv.id,
                        "rating": rating,
                        "reviewee_id": reviewee_id,
                        "reputation_change": delta,
                    },
                    user_id=current_user.id,
                )
                maybe_seal_block()
            except Exception:  # noqa: BLE001
                pass

            db.session.commit()
            flash("Review submitted.", "success")
            return redirect(url_for("request_detail", request_id=req.id))

        if request.method == "POST" and (offer_form.errors or review_form.errors or accept_form.errors or complete_form.errors):
            for field, errs in offer_form.errors.items():
                for e in errs:
                    flash(f"{field}: {e}", "error")
            for field, errs in review_form.errors.items():
                for e in errs:
                    flash(f"{field}: {e}", "error")
            for field, errs in accept_form.errors.items():
                for e in errs:
                    flash(f"{field}: {e}", "error")
            for field, errs in complete_form.errors.items():
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

        # Reviews for this request
        request_reviews = Review.query.filter_by(request_id=req.id).order_by(Review.created_at.desc()).all()

        # Eligibility to review
        can_review = False
        if req.status == "completed":
            completed_offer = HelpOffer.query.filter_by(request_id=req.id, status="completed").first()
            if completed_offer and (
                current_user.id in (req.user_id, completed_offer.helper_id)
            ):
                already = (
                    db.session.query(Review.id)
                    .filter_by(request_id=req.id, reviewer_id=current_user.id)
                    .first()
                )
                can_review = already is None

        return render_template(
            "features/request_detail.html",
            req=req,
            requester=requester,
            form=offer_form,
            review_form=review_form,
            accept_form=accept_form,
            complete_form=complete_form,
            all_offers=all_offers,
            is_requester=is_requester,
            my_offer=my_offer,
            request_reviews=request_reviews,
            can_review=can_review,
        )

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

    # ------------------
    # Admin: dashboard & users
    # ------------------
    @app.route("/admin")
    @login_required
    @admin_required
    def admin():
        from models import User, HelpRequest, Flag, NGO, Statement
        total_users = db.session.query(User).count()
        total_requests = db.session.query(HelpRequest).count()
        open_requests = db.session.query(HelpRequest).filter_by(status="open").count()
        completed_requests = db.session.query(HelpRequest).filter_by(status="completed").count()
        flagged_pending = db.session.query(Flag).filter_by(status="pending").count()
        recent_signups = User.query.order_by(User.created_at.desc()).limit(8).all()
        recent_activity = (
            Statement.query.order_by(Statement.created_at.desc()).limit(12).all()
        )
        return render_template(
            "admin/index.html",
            totals={
                "users": total_users,
                "requests": total_requests,
                "open_requests": open_requests,
                "completed_requests": completed_requests,
                "flagged": flagged_pending,
            },
            recent_signups=recent_signups,
            recent_activity=recent_activity,
        )

    @app.route("/admin/users")
    @login_required
    @admin_required
    def admin_users():
        from models import User
        q = request.args.get("q", "").strip()
        page = int(request.args.get("page", 1) or 1)
        per_page = 20
        query = User.query
        if q:
            like = f"%{q}%"
            query = query.filter((User.username.ilike(like)) | (User.email.ilike(like)) | (User.full_name.ilike(like)))
        users = query.order_by(User.created_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
        return render_template("admin/users.html", users=users, q=q)

    @app.post("/admin/users/<int:user_id>/blacklist")
    @login_required
    @admin_required
    def admin_blacklist_user(user_id: int):
        from models import User
        reason = (request.form.get("reason") or "").strip() or None
        u = User.query.get_or_404(user_id)
        u.is_blacklisted = True
        u.blacklist_reason = reason
        db.session.commit()

        # Blockchain log: user blacklisted
        try:
            append_statement(
                kind="admin_blacklist",
                payload={
                    "target_user_id": user_id,
                    "reason": reason,
                    "admin_id": current_user.id,
                },
                user_id=current_user.id,
            )
            maybe_seal_block()
        except Exception:  # noqa: BLE001
            pass

        flash("User blacklisted.", "success")
        return redirect(url_for("admin_users"))

    @app.post("/admin/users/<int:user_id>/unblacklist")
    @login_required
    @admin_required
    def admin_unblacklist_user(user_id: int):
        from models import User
        u = User.query.get_or_404(user_id)
        u.is_blacklisted = False
        u.blacklist_reason = None
        db.session.commit()

        # Blockchain log: user unblacklisted
        try:
            append_statement(
                kind="admin_unblacklist",
                payload={
                    "target_user_id": user_id,
                    "admin_id": current_user.id,
                },
                user_id=current_user.id,
            )
            maybe_seal_block()
        except Exception:  # noqa: BLE001
            pass

        flash("User unblacklisted.", "success")
        return redirect(url_for("admin_users"))

    @app.post("/admin/users/<int:user_id>/delete")
    @login_required
    @admin_required
    def admin_delete_user(user_id: int):
        from models import User
        u = User.query.get_or_404(user_id)
        db.session.delete(u)
        db.session.commit()

        # Blockchain log: user deleted
        try:
            append_statement(
                kind="admin_delete_user",
                payload={
                    "target_user_id": user_id,
                    "deleted_username": u.username,
                    "admin_id": current_user.id,
                },
                user_id=current_user.id,
            )
            maybe_seal_block()
        except Exception:  # noqa: BLE001
            pass

        flash("User deleted.", "success")
        return redirect(url_for("admin_users"))

    # ------------------
    # Admin: moderation (flags and NGO approvals)
    # ------------------
    @app.route("/admin/moderation")
    @login_required
    @admin_required
    def admin_moderation():
        from models import Flag, NGO
        flags = Flag.query.order_by(Flag.created_at.desc()).limit(50).all()
        pending_ngos = NGO.query.filter_by(verified_status=False).order_by(NGO.created_at.desc()).all()
        return render_template("admin/moderation.html", flags=flags, pending_ngos=pending_ngos)

    @app.post("/admin/flags/<int:flag_id>/<string:action>")
    @login_required
    @admin_required
    def admin_flag_action(flag_id: int, action: str):
        from models import Flag
        fl = Flag.query.get_or_404(flag_id)
        if action not in ("approve", "reject"):
            abort(400)
        fl.status = "approved" if action == "approve" else "rejected"
        db.session.commit()
        flash("Flag updated.", "success")
        return redirect(url_for("admin_moderation"))

    @app.post("/admin/ngos/<int:ngo_id>/verify")
    @login_required
    @admin_required
    def admin_verify_ngo(ngo_id: int):
        from models import NGO
        n = NGO.query.get_or_404(ngo_id)
        n.verified_status = True
        db.session.commit()

        # Blockchain log: NGO verified
        try:
            append_statement(
                kind="admin_verify_ngo",
                payload={
                    "ngo_id": ngo_id,
                    "ngo_name": n.name,
                    "admin_id": current_user.id,
                },
                user_id=current_user.id,
            )
            maybe_seal_block()
        except Exception:  # noqa: BLE001
            pass

        flash("NGO verified.", "success")
        return redirect(url_for("admin_moderation"))

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
            # Save lat/lng if provided
            try:
                user.latitude = float(form.latitude.data) if form.latitude.data is not None else None
            except Exception:
                user.latitude = None
            try:
                user.longitude = float(form.longitude.data) if form.longitude.data is not None else None
            except Exception:
                user.longitude = None
            db.session.commit()

            # Blockchain log: profile update
            try:
                append_statement(
                    kind="profile_update",
                    payload={
                        "updated_fields": [
                            field for field in ["full_name", "phone", "location", "bio", "skills", "avatar_url", "latitude", "longitude"]
                            if getattr(form, field).data is not None
                        ],
                    },
                    user_id=current_user.id,
                )
                maybe_seal_block()
            except Exception:  # noqa: BLE001
                pass

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
