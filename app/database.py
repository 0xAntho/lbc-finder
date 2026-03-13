from datetime import datetime
from sqlalchemy import (
    create_engine, Column, Integer, String, Boolean,
    Float, DateTime, ForeignKey, Text
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship

from app.config import DATABASE_URL

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    phone_number = Column(String, nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    alerts = relationship("Alert", back_populates="user")


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    city = Column(String, nullable=False)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    radius_km = Column(Integer, nullable=False, default=10)
    max_price = Column(Integer, nullable=True)
    min_surface = Column(Integer, nullable=True)
    min_land_surface = Column(Integer, nullable=True)
    min_outside_surface = Column(Integer, nullable=True)
    min_rooms = Column(Integer, nullable=True)
    is_active = Column(Boolean, default=True)
    last_checked_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="alerts")
    listings = relationship("Listing", back_populates="alert")


class Listing(Base):
    __tablename__ = "listings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    alert_id = Column(Integer, ForeignKey("alerts.id"), nullable=False)
    leboncoin_id = Column(String, nullable=False, unique=True)
    title = Column(String, nullable=True)
    price = Column(Integer, nullable=True)
    surface = Column(Integer, nullable=True)
    land_surface = Column(Integer, nullable=True)
    outside_surface = Column(Integer, nullable=True)
    rooms = Column(Integer, nullable=True)
    city = Column(String, nullable=True)
    url = Column(Text, nullable=True)
    published_at = Column(DateTime, nullable=True)
    notified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    alert = relationship("Alert", back_populates="listings")


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()