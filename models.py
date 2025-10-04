from datetime import datetime
from typing import Optional

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import db


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(50), nullable=True)
    location = db.Column(db.String(120), nullable=True)
    user_type = db.Column(db.String(20), nullable=False, default="user")  # admin/user
    is_blacklisted = db.Column(db.Boolean, nullable=False, default=False)
    reputation_score = db.Column(db.Float, nullable=False, default=0.0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    help_requests = db.relationship("HelpRequest", back_populates="user", lazy=True)
    help_offers = db.relationship(
        "HelpOffer", back_populates="helper", foreign_keys="HelpOffer.helper_id", lazy=True
    )

    reviews_written = db.relationship(
        "Review", back_populates="reviewer", foreign_keys="Review.reviewer_id", lazy=True
    )
    reviews_received = db.relationship(
        "Review", back_populates="reviewee", foreign_keys="Review.reviewee_id", lazy=True
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User {self.username}>"

    # Password helpers
    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class HelpRequest(db.Model):
    __tablename__ = "help_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(100), nullable=True)
    location = db.Column(db.String(120), nullable=True)
    time_needed = db.Column(db.String(120), nullable=True)
    price = db.Column(db.Float, nullable=True)
    is_volunteer = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(
        db.String(20), nullable=False, default="open"
    )  # open/in_progress/completed/cancelled
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = db.relationship("User", back_populates="help_requests")
    offers = db.relationship("HelpOffer", back_populates="request", lazy=True)
    reviews = db.relationship("Review", back_populates="request", lazy=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<HelpRequest {self.title} by {self.user_id}>"


class HelpOffer(db.Model):
    __tablename__ = "help_offers"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("help_requests.id"), nullable=False)
    helper_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    message = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), nullable=False, default="pending")  # pending/accepted/rejected
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    request = db.relationship("HelpRequest", back_populates="offers")
    helper = db.relationship("User", back_populates="help_offers")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<HelpOffer {self.id} on request {self.request_id} by {self.helper_id}>"


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("help_requests.id"), nullable=False)
    reviewer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    reviewee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    request = db.relationship("HelpRequest", back_populates="reviews")
    reviewer = db.relationship("User", foreign_keys=[reviewer_id], back_populates="reviews_written")
    reviewee = db.relationship("User", foreign_keys=[reviewee_id], back_populates="reviews_received")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Review {self.id} on request {self.request_id} {self.reviewer_id}->{self.reviewee_id}>"
