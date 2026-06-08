from datetime import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    nickname = db.Column(db.String(80), nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    contact = db.Column(db.String(256), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # 关系
    tasks = db.relationship('Task', backref='user', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<User {self.username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'nickname': self.nickname,
            'gender': self.gender,
            'contact': self.contact,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Task(db.Model):
    __tablename__ = 'tasks'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    due_date = db.Column(db.Date, nullable=True)
    completed = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    def __repr__(self):
        return f'<Task {self.id}: {self.title}>'

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'completed': self.completed,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Friendship(db.Model):
    __tablename__ = 'friendships'

    id = db.Column(db.Integer, primary_key=True)
    follower_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    followed_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    status = db.Column(db.String(20), default='pending')  # pending / accepted
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    follower = db.relationship('User', foreign_keys=[follower_id], backref='following')
    followed = db.relationship('User', foreign_keys=[followed_id], backref='followers')

    def to_dict(self):
        return {
            'id': self.id,
            'follower_id': self.follower_id,
            'followed_id': self.followed_id,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Trip(db.Model):
    __tablename__ = 'trips'

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=True)
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_private = db.Column(db.Boolean, default=False)
    visibility = db.Column(db.String(20), default='public')  # public / friends / private
    min_participants = db.Column(db.Integer, default=1)
    max_participants = db.Column(db.Integer, default=10)
    deadline = db.Column(db.DateTime, nullable=True)
    trigger_condition = db.Column(db.String(50), default='auto')  # auto / manual
    status = db.Column(db.String(20), default='recruiting')  # recruiting / confirmed / cancelled
    public_content = db.Column(db.Text, nullable=True)
    hidden_content = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    creator = db.relationship('User', backref='trips')

    def is_hidden(self):
        """判断内容是否应该隐藏"""
        if self.trigger_condition == 'manual':
            return self.status == 'confirmed'
        from datetime import datetime
        current = datetime.utcnow()
        participant_count = TripParticipant.query.filter_by(trip_id=self.id).count()
        if participant_count >= self.min_participants:
            return True
        if self.deadline and current >= self.deadline:
            return True
        return False

    def to_dict(self, include_hidden=False):
        result = {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'creator_id': self.creator_id,
            'is_private': self.is_private,
            'visibility': self.visibility,
            'min_participants': self.min_participants,
            'max_participants': self.max_participants,
            'deadline': self.deadline.isoformat() if self.deadline else None,
            'trigger_condition': self.trigger_condition,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'creator': self.creator.to_dict() if self.creator else None,
            'participant_count': TripParticipant.query.filter_by(trip_id=self.id).count()
        }
        if include_hidden or not self.is_hidden():
            result['public_content'] = self.public_content
            result['hidden_content'] = self.hidden_content
        return result


class TripApplication(db.Model):
    __tablename__ = 'trip_applications'

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending / approved / rejected
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)

    trip = db.relationship('Trip', backref='applications')
    applicant = db.relationship('User', backref='trip_applications')

    def to_dict(self):
        return {
            'id': self.id,
            'trip_id': self.trip_id,
            'applicant_id': self.applicant_id,
            'status': self.status,
            'applied_at': self.applied_at.isoformat() if self.applied_at else None,
            'applicant': self.applicant.to_dict() if self.applicant else None
        }


class TripParticipant(db.Model):
    __tablename__ = 'trip_participants'

    id = db.Column(db.Integer, primary_key=True)
    trip_id = db.Column(db.Integer, db.ForeignKey('trips.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)

    trip = db.relationship('Trip', backref='participants')
    user = db.relationship('User', backref='trip_participations')

    def to_dict(self):
        return {
            'id': self.id,
            'trip_id': self.trip_id,
            'user_id': self.user_id,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None,
            'user': self.user.to_dict() if self.user else None
        }