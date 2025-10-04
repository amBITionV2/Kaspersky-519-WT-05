from flask_wtf import FlaskForm
from wtforms import (
    StringField,
    PasswordField,
    BooleanField,
    SubmitField,
    TextAreaField,
    SelectField,
    DecimalField,
)
from wtforms.fields.datetime import DateTimeLocalField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Optional
from wtforms.validators import NumberRange


class SignUpForm(FlaskForm):
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=80)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match")],
    )
    full_name = StringField("Full Name", validators=[Optional(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    location = StringField("Location", validators=[Optional(), Length(max=120)])
    submit = SubmitField("Sign Up")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=120)])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember me")
    submit = SubmitField("Log In")


class RequestHelpForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=10)])
    category = SelectField(
        "Category",
        choices=[
            ("Cooking", "Cooking"),
            ("Cleaning", "Cleaning"),
            ("Moving", "Moving"),
            ("Tutoring", "Tutoring"),
            ("Errands", "Errands"),
            ("Technical", "Technical"),
            ("Other", "Other"),
        ],
        validators=[DataRequired()],
    )
    location = StringField("Location", validators=[Optional(), Length(max=120)])
    datetime_needed = DateTimeLocalField(
        "Date & Time needed", format="%Y-%m-%dT%H:%M", validators=[Optional()]
    )
    duration_estimate = StringField("Duration estimate", validators=[Optional(), Length(max=120)])
    price_offered = DecimalField("Price offered", places=2, rounding=None, validators=[Optional()])
    is_volunteer = BooleanField("This is a volunteer/free request")
    skills_required = StringField("Skills required", validators=[Optional(), Length(max=200)])
    notes = TextAreaField("Additional notes", validators=[Optional(), Length(max=1000)])
    submit = SubmitField("Post Request")


class OfferHelpForm(FlaskForm):
    message = TextAreaField("Message to requester", validators=[DataRequired(), Length(min=5, max=2000)])
    availability = BooleanField("I am available and can start")
    timeframe = StringField("Expected completion timeframe", validators=[Optional(), Length(max=120)])
    submit = SubmitField("Submit Offer")


class NGOForm(FlaskForm):
    name = StringField("NGO Name", validators=[DataRequired(), Length(max=200)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=20)])
    category = SelectField(
        "Category",
        choices=[
            ("Education", "Education"),
            ("Healthcare", "Healthcare"),
            ("Environment", "Environment"),
            ("Poverty Alleviation", "Poverty Alleviation"),
            ("Animal Welfare", "Animal Welfare"),
            ("Women & Children", "Women & Children"),
            ("Disaster Relief", "Disaster Relief"),
            ("Other", "Other"),
        ],
        validators=[Optional()],
    )
    location = StringField("Location", validators=[Optional(), Length(max=200)])
    contact_email = StringField("Contact Email", validators=[Optional(), Email(), Length(max=200)])
    website = StringField("Website", validators=[Optional(), Length(max=300)])
    submit = SubmitField("Submit for Approval")


class ProfileForm(FlaskForm):
    full_name = StringField("Full Name", validators=[Optional(), Length(max=120)])
    phone = StringField("Phone", validators=[Optional(), Length(max=50)])
    location = StringField("Location", validators=[Optional(), Length(max=120)])
    bio = TextAreaField("About", validators=[Optional(), Length(max=2000)])
    skills = StringField("Skills", validators=[Optional(), Length(max=300)])
    avatar_url = StringField("Profile Picture URL", validators=[Optional(), Length(max=300)])
    latitude = DecimalField("Latitude", places=6, rounding=None, validators=[Optional(), NumberRange(min=-90, max=90)])
    longitude = DecimalField("Longitude", places=6, rounding=None, validators=[Optional(), NumberRange(min=-180, max=180)])
    submit = SubmitField("Save Changes")


class ReviewForm(FlaskForm):
    rating = SelectField(
        "Rating",
        choices=[("5", "★★★★★"), ("4", "★★★★"), ("3", "★★★"), ("2", "★★"), ("1", "★")],
        validators=[DataRequired()],
    )
    comment = TextAreaField("Review", validators=[Optional(), Length(max=2000)])
    submit = SubmitField("Submit Review")
