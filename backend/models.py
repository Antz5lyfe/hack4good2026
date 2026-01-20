"""
SQLAlchemy Database Models for CareConnect Platform
Implements User, Activity, and Booking tables with membership tier logic
"""
from datetime import datetime
from sqlalchemy import create_engine, Column, Integer, String, DateTime, ForeignKey, Enum, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
import enum

Base = declarative_base()


class MembershipTier(enum.Enum):
    """Membership tier enum defining weekly token allowances"""
    ADHOC = "Adhoc"  # 0 tokens - pay per booking
    WEEKLY_1 = "Weekly_1"  # 1 token per week
    WEEKLY_2 = "Weekly_2"  # 2 tokens per week
    UNLIMITED = "Unlimited"  # Unlimited tokens


class UserRole(enum.Enum):
    """User role types in the system"""
    PARTICIPANT = "Participant"
    CAREGIVER = "Caregiver"
    STAFF = "Staff"
    VOLUNTEER = "Volunteer"


class BookingStatus(enum.Enum):
    """Booking status states"""
    CONFIRMED = "Confirmed"
    WAITLIST = "Waitlist"
    CANCELLED = "Cancelled"


class User(Base):
    """
    User model representing participants, caregivers, staff, and volunteers
    
    CRITICAL: 
    - membership_tier Enum controls weekly token limits
    - medical_flags JSON stores accessibility requirements (wheelchair, seizure_risk, etc.)
    """
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    email = Column(String(120), unique=True, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.PARTICIPANT)
    membership_tier = Column(Enum(MembershipTier), nullable=False, default=MembershipTier.ADHOC)
    
    # JSON field for medical/accessibility flags
    # Example: {"wheelchair": true, "seizure_risk": false, "dietary_restrictions": ["vegetarian"]}
    medical_flags = Column(JSON, default=dict)
    
    # For caregivers managing dependents
    linked_account_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = relationship("Booking", back_populates="user", foreign_keys="Booking.user_id")
    linked_accounts = relationship("User", remote_side=[id])
    
    def __repr__(self):
        return f"<User(id={self.id}, name='{self.name}', tier={self.membership_tier.value})>"
    
    def get_weekly_token_limit(self):
        """Returns the weekly token limit based on membership tier"""
        token_limits = {
            MembershipTier.ADHOC: 0,
            MembershipTier.WEEKLY_1: 1,
            MembershipTier.WEEKLY_2: 2,
            MembershipTier.UNLIMITED: float('inf')
        }
        return token_limits.get(self.membership_tier, 0)


class Activity(Base):
    """
    Activity model representing events/classes
    
    CRITICAL:
    - volunteer_slots is used for capacity calculation
    - Capacity formula: base_capacity + (volunteer_count * 2)
    """
    __tablename__ = 'activities'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String(200), nullable=False)
    description = Column(String(500))
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    location = Column(String(200))
    
    # Capacity management
    base_capacity = Column(Integer, nullable=False, default=10)
    volunteer_slots = Column(Integer, nullable=False, default=0)  # CRITICAL for capacity logic
    
    # Activity requirements as JSON
    # Example: {"accessible": true, "payment_required": false, "age_min": 18}
    requirements = Column(JSON, default=dict)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    bookings = relationship("Booking", back_populates="activity")
    
    def __repr__(self):
        return f"<Activity(id={self.id}, title='{self.title}', capacity={self.base_capacity})>"
    
    def get_current_capacity(self, session):
        """
        Calculate dynamic capacity based on volunteer participation
        Formula: base_capacity + (volunteer_count * 2)
        """
        from sqlalchemy import func
        
        # Count confirmed volunteer bookings
        volunteer_count = session.query(func.count(Booking.id))\
            .join(User)\
            .filter(
                Booking.activity_id == self.id,
                Booking.status == BookingStatus.CONFIRMED,
                User.role == UserRole.VOLUNTEER
            ).scalar() or 0
        
        return self.base_capacity + (volunteer_count * 2)
    
    def get_current_attendees(self, session):
        """Get count of confirmed participant bookings (excluding volunteers)"""
        from sqlalchemy import func
        
        attendee_count = session.query(func.count(Booking.id))\
            .join(User)\
            .filter(
                Booking.activity_id == self.id,
                Booking.status == BookingStatus.CONFIRMED,
                User.role != UserRole.VOLUNTEER
            ).scalar() or 0
        
        return attendee_count
    
    def is_accessible(self):
        """Check if activity is wheelchair accessible"""
        return self.requirements.get('accessible', False)


class Booking(Base):
    """
    Booking model representing the join table between Users and Activities
    Tracks reservation status and timestamps
    """
    __tablename__ = 'bookings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    activity_id = Column(Integer, ForeignKey('activities.id'), nullable=False)
    status = Column(Enum(BookingStatus), nullable=False, default=BookingStatus.CONFIRMED)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="bookings", foreign_keys=[user_id])
    activity = relationship("Activity", back_populates="bookings")
    
    def __repr__(self):
        return f"<Booking(id={self.id}, user_id={self.user_id}, activity_id={self.activity_id}, status={self.status.value})>"


# Database engine initialization helper
def init_db(database_url='sqlite:///careconnect.db'):
    """Initialize the database and create all tables"""
    engine = create_engine(database_url, echo=True)
    Base.metadata.create_all(engine)
    return engine
