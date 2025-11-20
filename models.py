from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import CheckConstraint, UniqueConstraint
import uuid

# Initialize SQLAlchemy (app must call db.init_app(app))
db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    userId = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    passwordHash = db.Column(db.String(255), nullable=False)
    createdTime = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    isActive = db.Column(db.Boolean, default=True)
    role = db.Column(db.String(20), default='user')
    __table_args__ = (
        CheckConstraint(role.in_(['user', 'admin']), name='chk_role'),
    )

class ProfilePreference(db.Model):
    __tablename__ = 'profilePreferences'
    userId = db.Column(UUID(as_uuid=True), primary_key=True)
    demographic = db.Column(JSONB)
    preferredGenres = db.Column(JSONB)
    preferredStudios = db.Column(JSONB)
    preferredThemes = db.Column(JSONB)
    filterSettings = db.Column(JSONB)
    tasteSurvey = db.Column(JSONB)
    updateTime = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

class Anime(db.Model):
    __tablename__ = 'animeCatalog'
    animeId = db.Column(db.String(32), primary_key=True)
    coreRecord = db.Column(JSONB, nullable=False)
    aboutMe = db.Column(JSONB)
    popularity = db.Column(JSONB)
    status = db.Column(db.String(20), default='active')
    dataFingerprint = db.Column(db.String(64), unique=True)
    updateTime = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

class Rating(db.Model):
    __tablename__ = 'ratingSnapshots'
    ratingId = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId = db.Column(UUID(as_uuid=True), nullable=False)
    animeId = db.Column(db.String(32), nullable=False)
    score = db.Column(db.SmallInteger, nullable=False)
    ratingMeta = db.Column(JSONB)
    reviewText = db.Column(db.Text)
    createTime = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    __table_args__ = (
        UniqueConstraint('userId', 'animeId'),
        CheckConstraint('score >= 0 AND score <= 10'),
    )

class RatingHistory(db.Model):
    __tablename__ = 'ratingHistory'
    historyId = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ratingId = db.Column(UUID(as_uuid=True), nullable=False)
    priorPayload = db.Column(JSONB, nullable=False)
    changedAt = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

class Watchlist(db.Model):
    __tablename__ = 'watchlistDocuments'
    watchlistId = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId = db.Column(UUID(as_uuid=True), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    items = db.Column(JSONB, nullable=False)
    watchlistMetadata = db.Column(JSONB)
    createTime = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    updateTime = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

class UserNote(db.Model):
    __tablename__ = 'userNotes'
    noteId = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId = db.Column(UUID(as_uuid=True), nullable=False)
    animeId = db.Column(db.String(32), nullable=False)
    noteText = db.Column(db.Text)
    tags = db.Column(JSONB)
    noteHash = db.Column(db.String(64), unique=True)
    private = db.Column(db.Boolean, default=True)
    createTime = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

class RecommendationCache(db.Model):
    __tablename__ = 'recommendationCache'
    cacheId = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId = db.Column(UUID(as_uuid=True), unique=True, nullable=False)
    payload = db.Column(JSONB, nullable=False)
    sourceMetadata = db.Column(JSONB)
    confidenceScore = db.Column(db.Float)
    updatedAt = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

class RecommendationAudit(db.Model):
    __tablename__ = 'recommendationAudit'
    auditId = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId = db.Column(UUID(as_uuid=True), nullable=False)
    recommendationSnapshot = db.Column(JSONB, nullable=False)
    generatedBy = db.Column(db.String(50))
    generatedAt = db.Column(db.DateTime(timezone=True), server_default=db.func.now())

class RatingEventsLog(db.Model):
    __tablename__ = 'ratingEventsLog'
    eventId = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId = db.Column(UUID(as_uuid=True))
    animeId = db.Column(db.String(32))
    score = db.Column(db.SmallInteger, nullable=False)
    eventTime = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    payload = db.Column(JSONB)
    __table_args__ = (
        CheckConstraint('score >= 0 AND score <= 10'),
    )

class SearchEventsLog(db.Model):
    __tablename__ = 'searchEventsLog'
    eventId = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    userId = db.Column(UUID(as_uuid=True))
    searchQuery = db.Column(db.Text)
    filters = db.Column(JSONB)
    eventTime = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    payload = db.Column(JSONB)

class ImportJob(db.Model):
    __tablename__ = 'importJobs'
    jobId = db.Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    adminUserId = db.Column(UUID(as_uuid=True))
    status = db.Column(db.String(20), default='pending')
    payload = db.Column(JSONB, nullable=False)
    startedAt = db.Column(db.DateTime(timezone=True), server_default=db.func.now())
    completedAt = db.Column(db.DateTime(timezone=True))

