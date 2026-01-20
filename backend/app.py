"""
Flask Application - CareConnect Backend API
RESTful endpoints for booking management with Dynamic Token system
"""
from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import datetime, timedelta
import os

from models import Base, User, Activity, Booking, MembershipTier, UserRole, BookingStatus
from booking_service import (
    attempt_booking, 
    get_user_token_balance, 
    cancel_booking,
    BookingError
)

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = 'careconnect-secret-key-2026'
CORS(app)  # Enable CORS for frontend integration

# Database setup
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///careconnect.db')
engine = create_engine(DATABASE_URL, echo=False)
session_factory = sessionmaker(bind=engine)
Session = scoped_session(session_factory)

# Create tables
Base.metadata.create_all(engine)


def seed_test_data():
    """Seed the database with test data for demonstration"""
    session = Session()
    
    # Check if data already exists
    if session.query(User).count() > 0:
        session.close()
        return
    
    print("Seeding test data...")
    
    # Create test users with different membership tiers
    users = [
        User(
            name="Alice Tan",
            email="alice@example.com",
            role=UserRole.PARTICIPANT,
            membership_tier=MembershipTier.WEEKLY_1,
            medical_flags={"wheelchair": False, "seizure_risk": False}
        ),
        User(
            name="Bob Chen (Wheelchair User)",
            email="bob@example.com",
            role=UserRole.PARTICIPANT,
            membership_tier=MembershipTier.WEEKLY_2,
            medical_flags={"wheelchair": True, "seizure_risk": False}
        ),
        User(
            name="Carol Lim (Premium)",
            email="carol@example.com",
            role=UserRole.PARTICIPANT,
            membership_tier=MembershipTier.UNLIMITED,
            medical_flags={"wheelchair": False, "seizure_risk": True}
        ),
        User(
            name="David Ng (Ad-hoc)",
            email="david@example.com",
            role=UserRole.PARTICIPANT,
            membership_tier=MembershipTier.ADHOC,
            medical_flags={}
        ),
        User(
            name="Emma Wong (Volunteer)",
            email="emma@example.com",
            role=UserRole.VOLUNTEER,
            membership_tier=MembershipTier.ADHOC,  # Volunteers don't use tokens
            medical_flags={}
        ),
        User(
            name="Frank Lee (Staff)",
            email="frank@example.com",
            role=UserRole.STAFF,
            membership_tier=MembershipTier.UNLIMITED,
            medical_flags={}
        )
    ]
    
    session.add_all(users)
    session.commit()
    
    # Create test activities
    base_time = datetime.utcnow() + timedelta(days=1)
    
    activities = [
        Activity(
            title="Morning Yoga Session",
            description="Gentle yoga for all skill levels",
            start_time=base_time.replace(hour=9, minute=0),
            end_time=base_time.replace(hour=10, minute=30),
            location="Community Hall A",
            base_capacity=10,
            volunteer_slots=3,
            requirements={"accessible": True, "payment_required": False}
        ),
        Activity(
            title="Art & Craft Workshop",
            description="Creative painting session",
            start_time=base_time.replace(hour=14, minute=0),
            end_time=base_time.replace(hour=16, minute=0),
            location="Art Studio (2nd Floor)",
            base_capacity=8,
            volunteer_slots=2,
            requirements={"accessible": False, "payment_required": False}  # Not wheelchair accessible
        ),
        Activity(
            title="Social Dance Class",
            description="Fun social dancing for everyone",
            start_time=base_time.replace(hour=18, minute=30),
            end_time=base_time.replace(hour=20, minute=0),
            location="Main Hall",
            base_capacity=15,
            volunteer_slots=4,
            requirements={"accessible": True, "payment_required": False}
        ),
        Activity(
            title="Music Therapy",
            description="Relaxing music therapy session",
            start_time=(base_time + timedelta(days=1)).replace(hour=10, minute=0),
            end_time=(base_time + timedelta(days=1)).replace(hour=11, minute=30),
            location="Therapy Room",
            base_capacity=6,
            volunteer_slots=1,
            requirements={"accessible": True, "payment_required": False}
        )
    ]
    
    session.add_all(activities)
    session.commit()
    session.close()
    
    print("Test data seeded successfully!")


# Seed data on startup
with app.app_context():
    seed_test_data()


# ========================================================================
# API ENDPOINTS
# ========================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "CareConnect API"}), 200


@app.route('/api/book', methods=['POST'])
def create_booking():
    """
    POST /api/book
    Create a new booking with Dynamic Token validation
    
    Request Body:
        {
            "user_id": int,
            "activity_id": int
        }
    
    Returns:
        200: Booking successful
        400: Validation failed (token limit, capacity, accessibility)
        404: User or activity not found
    """
    session = Session()
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        activity_id = data.get('activity_id')
        
        if not user_id or not activity_id:
            return jsonify({
                "success": False,
                "error": "Missing user_id or activity_id"
            }), 400
        
        # Call the booking service
        result = attempt_booking(session, user_id, activity_id)
        
        return jsonify(result), 200
        
    except BookingError as e:
        return jsonify({
            "success": False,
            "error": e.message,
            "error_code": e.error_code
        }), 400
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": f"Internal server error: {str(e)}"
        }), 500
        
    finally:
        session.close()


@app.route('/api/user/<int:user_id>/tokens', methods=['GET'])
def get_tokens(user_id):
    """
    GET /api/user/<user_id>/tokens
    Get user's token balance for the current week
    
    Returns:
        {
            "tokens_total": int | "Unlimited",
            "tokens_used": int,
            "tokens_remaining": int | "Unlimited"
        }
    """
    session = Session()
    
    try:
        balance = get_user_token_balance(session, user_id)
        return jsonify(balance), 200
        
    except BookingError as e:
        return jsonify({
            "success": False,
            "error": e.message
        }), 404
        
    finally:
        session.close()


@app.route('/api/activities', methods=['GET'])
def get_activities():
    """
    GET /api/activities
    Get list of all activities with current capacity info
    
    Query Params:
        user_id (optional): Filter activities based on user's accessibility needs
    """
    session = Session()
    
    try:
        user_id = request.args.get('user_id', type=int)
        activities = session.query(Activity).all()
        
        # If user_id provided, filter based on medical flags
        if user_id:
            user = session.query(User).filter(User.id == user_id).first()
            if user:
                user_medical_flags = user.medical_flags or {}
                requires_wheelchair = user_medical_flags.get('wheelchair', False)
                
                # Filter out non-accessible activities for wheelchair users
                if requires_wheelchair:
                    activities = [a for a in activities if a.is_accessible()]
        
        result = []
        for activity in activities:
            current_capacity = activity.get_current_capacity(session)
            current_attendees = activity.get_current_attendees(session)
            
            result.append({
                "id": activity.id,
                "title": activity.title,
                "description": activity.description,
                "start_time": activity.start_time.isoformat(),
                "end_time": activity.end_time.isoformat() if activity.end_time else None,
                "location": activity.location,
                "base_capacity": activity.base_capacity,
                "current_capacity": current_capacity,
                "current_attendees": current_attendees,
                "available_slots": max(0, current_capacity - current_attendees),
                "volunteer_slots": activity.volunteer_slots,
                "requirements": activity.requirements,
                "is_accessible": activity.is_accessible()
            })
        
        return jsonify({"activities": result}), 200
        
    finally:
        session.close()


@app.route('/api/activities/<int:activity_id>', methods=['GET'])
def get_activity(activity_id):
    """Get details of a specific activity"""
    session = Session()
    
    try:
        activity = session.query(Activity).filter(Activity.id == activity_id).first()
        
        if not activity:
            return jsonify({"error": "Activity not found"}), 404
        
        current_capacity = activity.get_current_capacity(session)
        current_attendees = activity.get_current_attendees(session)
        
        # Get list of bookings
        bookings = session.query(Booking).filter(
            Booking.activity_id == activity_id,
            Booking.status == BookingStatus.CONFIRMED
        ).all()
        
        booking_list = []
        for booking in bookings:
            user = session.query(User).filter(User.id == booking.user_id).first()
            booking_list.append({
                "booking_id": booking.id,
                "user_name": user.name,
                "user_role": user.role.value,
                "booked_at": booking.created_at.isoformat()
            })
        
        return jsonify({
            "id": activity.id,
            "title": activity.title,
            "description": activity.description,
            "start_time": activity.start_time.isoformat(),
            "end_time": activity.end_time.isoformat() if activity.end_time else None,
            "location": activity.location,
            "base_capacity": activity.base_capacity,
            "current_capacity": current_capacity,
            "current_attendees": current_attendees,
            "available_slots": max(0, current_capacity - current_attendees),
            "volunteer_slots": activity.volunteer_slots,
            "requirements": activity.requirements,
            "is_accessible": activity.is_accessible(),
            "bookings": booking_list
        }), 200
        
    finally:
        session.close()


@app.route('/api/activities', methods=['POST'])
def create_activity():
    """
    POST /api/activities
    Create a new activity (Staff only in production)
    """
    session = Session()
    
    try:
        data = request.get_json()
        
        activity = Activity(
            title=data.get('title'),
            description=data.get('description', ''),
            start_time=datetime.fromisoformat(data.get('start_time')),
            end_time=datetime.fromisoformat(data.get('end_time')) if data.get('end_time') else None,
            location=data.get('location', ''),
            base_capacity=data.get('base_capacity', 10),
            volunteer_slots=data.get('volunteer_slots', 0),
            requirements=data.get('requirements', {})
        )
        
        session.add(activity)
        session.commit()
        session.refresh(activity)
        
        return jsonify({
            "success": True,
            "activity_id": activity.id,
            "message": "Activity created successfully"
        }), 201
        
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400
        
    finally:
        session.close()


@app.route('/api/booking/<int:booking_id>/cancel', methods=['POST'])
def cancel_booking_endpoint(booking_id):
    """
    POST /api/booking/<booking_id>/cancel
    Cancel a booking
    """
    session = Session()
    
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id required"}), 400
        
        result = cancel_booking(session, booking_id, user_id)
        return jsonify(result), 200
        
    except BookingError as e:
        return jsonify({
            "success": False,
            "error": e.message
        }), 400
        
    finally:
        session.close()


@app.route('/api/users', methods=['GET'])
def get_users():
    """GET /api/users - List all users (for testing)"""
    session = Session()
    
    try:
        users = session.query(User).all()
        result = []
        
        for user in users:
            result.append({
                "id": user.id,
                "name": user.name,
                "email": user.email,
                "role": user.role.value,
                "membership_tier": user.membership_tier.value,
                "medical_flags": user.medical_flags
            })
        
        return jsonify({"users": result}), 200
        
    finally:
        session.close()


if __name__ == '__main__':
    print("=" * 60)
    print("CareConnect Backend API")
    print("Dynamic Token Booking System")
    print("=" * 60)
    print("\nAPI Endpoints:")
    print("  POST   /api/book                    - Create booking")
    print("  GET    /api/user/<id>/tokens        - Get token balance")
    print("  GET    /api/activities              - List activities")
    print("  GET    /api/activities/<id>         - Get activity details")
    print("  POST   /api/activities              - Create activity")
    print("  POST   /api/booking/<id>/cancel     - Cancel booking")
    print("  GET    /api/users                   - List users")
    print("\n" + "=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
