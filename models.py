from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from enum import Enum

db = SQLAlchemy()

# --------------------
# ENUMS
# --------------------

class PostCategory(Enum):
    GENERAL = "general"
    QUESTION = "question"
    ADVICE = "advice"
    EXPERIENCE = "experience"


# --------------------
# POST VIEW (analytics)
# --------------------

class PostView(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', name='unique_post_view'),
    )


# --------------------
# ACADEMIC FEATURES
# --------------------

class AcademicFeatures(db.Model):
    """
    Types:
    - realism_score (1–10)
    - is_experience (1)
    - is_wish_knew (1)
    """
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(20), nullable=False)
    value = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('post_id', 'user_id', 'type', name='unique_academic_vote'),
    )


# --------------------
# USER
# --------------------

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)

    university = db.Column(db.String(120))
    position = db.Column(db.String(120))  # Student, Professor, Alumni
    bio = db.Column(db.String(500))

    is_admin = db.Column(db.Boolean, default=False)

    # Verification (CV parlatıcı detay)
    is_verified = db.Column(db.Boolean, default=False)
    verification_type = db.Column(db.String(50))  # student_email, academic_email, alumni

    # Profile Image
    profile_image = db.Column(db.String(150), default='default.png')

    # Ban system
    is_banned = db.Column(db.Boolean, default=False)
    ban_reason = db.Column(db.String(255))
    ban_appeal_reason = db.Column(db.Text)  # Appeal text
    ban_expires_at = db.Column(db.DateTime)

    agreed_kvkk = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    last_username_change = db.Column(db.DateTime) # Track last username change

    posts = db.relationship('Post', backref='author', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='author', lazy=True, cascade="all, delete-orphan")
    
    # Cascade deletes for other user-related data
    votes = db.relationship('Vote', backref='user', lazy=True, cascade="all, delete-orphan")
    academic_votes = db.relationship('AcademicFeatures', backref='user', lazy=True, cascade="all, delete-orphan")
    post_views = db.relationship('PostView', backref='user', lazy=True, cascade="all, delete-orphan")
    
    # Relationships for reports (defined below in Report class but added here for clarity if needed, 
    # though backrefs in Report handle it)

    @property
    def can_change_username(self):
        if not self.last_username_change:
            return True
        return datetime.utcnow() > self.last_username_change + timedelta(days=7)

    @property
    def days_until_username_change(self):
        if not self.last_username_change:
            return 0
        delta = (self.last_username_change + timedelta(days=7)) - datetime.utcnow()
        return delta.days + 1

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


# --------------------
# POST
# --------------------

class Post(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)

    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    category = db.Column(db.Enum(PostCategory), nullable=False)

    # Cached counters
    view_count = db.Column(db.Integer, default=0)

    comments = db.relationship(
        'Comment',
        backref='post',
        lazy=True,
        cascade="all, delete-orphan"
    )

    votes = db.relationship(
        'Vote',
        backref='post',
        lazy=True,
        cascade="all, delete-orphan"
    )

    academic_votes = db.relationship(
        'AcademicFeatures',
        backref='post',
        lazy=True,
        cascade="all, delete-orphan"
    )

    post_views = db.relationship(
        'PostView',
        backref='related_post', # distinct name from post_id
        lazy=True,
        cascade="all, delete-orphan"
    )

    @property
    def score(self):
        return sum(v.value for v in self.votes)

    @property
    def like_count(self):
        return len([v for v in self.votes if v.value == 1])

    @property
    def dislike_count(self):
        return len([v for v in self.votes if v.value == -1])


    @property
    def realism_average(self):
        scores = [v.value for v in self.academic_votes if v.type == "realism_score"]
        if not scores:
            return 0
        return round(sum(scores) / len(scores), 1)

    @property
    def experience_count(self):
        return len([v for v in self.academic_votes if v.type == "is_experience"])

    @property
    def wish_knew_count(self):
        return len([v for v in self.academic_votes if v.type == "is_wish_knew"])


    @property
    def category_label(self):
        labels = {
            PostCategory.GENERAL: "Genel",
            PostCategory.QUESTION: "Soru & Cevap",
            PostCategory.ADVICE: "Tavsiye",
            PostCategory.EXPERIENCE: "Deneyim"
        }
        return labels.get(self.category, "Genel")


# --------------------
# COMMENT
# --------------------

class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)

    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

    created_at = db.Column(db.DateTime, default=datetime.now) # Changed to datetime.now for local time awareness potential but usually handled by tz
    is_hidden = db.Column(db.Boolean, default=False)
    
    # Self-referential relationship for nesting
    parent_id = db.Column(db.Integer, db.ForeignKey('comment.id'), nullable=True)
    replies = db.relationship('Comment', backref=db.backref('parent', remote_side=[id]), lazy=True, cascade="all, delete-orphan")


# --------------------
# VOTE
# --------------------

class Vote(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=False)

    value = db.Column(db.Integer, nullable=False)  # 1 or -1

    __table_args__ = (
        db.UniqueConstraint('user_id', 'post_id', name='unique_user_post_vote'),
    )


# --------------------
# REPORT
# --------------------

class Report(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    
    # Can report a user OR a post
    reported_user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    reported_post_id = db.Column(db.Integer, db.ForeignKey('post.id'), nullable=True)
    
    reason = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_resolved = db.Column(db.Boolean, default=False)

    reporter = db.relationship('User', foreign_keys=[reporter_id], backref=db.backref('reports_made', cascade="all, delete-orphan"))
    reported_user = db.relationship('User', foreign_keys=[reported_user_id], backref=db.backref('reports_received', cascade="all, delete-orphan"))
    reported_post = db.relationship('Post', backref=db.backref('reports', cascade="all, delete-orphan"))
