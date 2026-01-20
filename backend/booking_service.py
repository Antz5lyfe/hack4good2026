"""
Booking Service - Core Business Logic for CareConnect
Implements the "Dynamic Token" booking system with three-tier validation
"""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from models import User, Activity, Booking, BookingStatus, MembershipTier, UserRole


class BookingError(Exception):
    """Custom exception for booking validation failures"""
    def __init__(self, message, error_code):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


def get_week_start_end():
    """
    Get the start and end datetime for the current week (Monday to Sunday)
    Used for weekly token calculations
    """
    now = datetime.utcnow()
    # Get Monday of current week (weekday 0 = Monday)
    start_of_week = now - timedelta(days=now.weekday())
    start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_week = start_of_week + timedelta(days=7)
    return start_of_week, end_of_week


def attempt_booking(session: Session, user_id: int, activity_id: int):
    """
    Core booking function implementing the Dynamic Token logic with three validation checks
    
    CHECK 1 (MEMBERSHIP): Verify user has available tokens this week based on tier
    CHECK 2 (CAPACITY): Verify activity has space (base_capacity + volunteer_count * 2)
    CHECK 3 (MEDICAL): Verify accessibility requirements match user's medical flags
    
    Args:
        session: SQLAlchemy database session
        user_id: ID of the user attempting to book
        activity_id: ID of the activity to book
        
    Returns:
        dict: Success response with booking details
        
    Raises:
        BookingError: If any validation check fails
    """
    
    # Fetch user and activity from database
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise BookingError("User not found", "USER_NOT_FOUND")
    
    activity = session.query(Activity).filter(Activity.id == activity_id).first()
    if not activity:
        raise BookingError("Activity not found", "ACTIVITY_NOT_FOUND")
    
    # Check if user already has a booking for this activity
    existing_booking = session.query(Booking).filter(
        Booking.user_id == user_id,
        Booking.activity_id == activity_id,
        Booking.status == BookingStatus.CONFIRMED
    ).first()
    
    if existing_booking:
        raise BookingError("You have already booked this activity", "DUPLICATE_BOOKING")
    
    # ========================================================================
    # CHECK 1: MEMBERSHIP TIER TOKEN VALIDATION
    # ========================================================================
    # Query how many bookings the user has this week vs. their tier limit
    
    if user.role != UserRole.VOLUNTEER:  # Volunteers don't consume tokens
        start_of_week, end_of_week = get_week_start_end()
        
        # Count confirmed bookings this week (excluding volunteer bookings)
        weekly_bookings_count = session.query(Booking).filter(
            Booking.user_id == user_id,
            Booking.status == BookingStatus.CONFIRMED,
            Booking.created_at >= start_of_week,
            Booking.created_at < end_of_week
        ).count()
        
        # Get user's weekly token limit based on membership tier
        token_limit = user.get_weekly_token_limit()
        
        # Ad-hoc members need payment redirection
        if user.membership_tier == MembershipTier.ADHOC:
            raise BookingError(
                "Ad-hoc members must complete payment before booking",
                "PAYMENT_REQUIRED"
            )
        
        # Check if user has exceeded their weekly token limit
        if token_limit != float('inf') and weekly_bookings_count >= token_limit:
            raise BookingError(
                f"Weekly Token Limit Reached. You have used {weekly_bookings_count}/{token_limit} tokens this week.",
                "TOKEN_LIMIT_REACHED"
            )
    
    # ========================================================================
    # CHECK 2: CAPACITY VALIDATION
    # ========================================================================
    # Check if current_attendees < (base_capacity + (volunteer_count * 2))
    
    current_capacity = activity.get_current_capacity(session)
    current_attendees = activity.get_current_attendees(session)
    
    # Volunteers increase capacity, so they bypass participant capacity checks
    if user.role == UserRole.VOLUNTEER:
        # Check volunteer slots availability
        current_volunteer_count = session.query(Booking).join(User).filter(
            Booking.activity_id == activity_id,
            Booking.status == BookingStatus.CONFIRMED,
            User.role == UserRole.VOLUNTEER
        ).count()
        
        if current_volunteer_count >= activity.volunteer_slots:
            raise BookingError(
                f"All volunteer slots are filled ({current_volunteer_count}/{activity.volunteer_slots})",
                "VOLUNTEER_SLOTS_FULL"
            )
    else:
        # Check participant capacity
        if current_attendees >= current_capacity:
            raise BookingError(
                f"Activity at capacity ({current_attendees}/{current_capacity} attendees)",
                "ACTIVITY_FULL"
            )
    
    # ========================================================================
    # CHECK 3: MEDICAL ACCESSIBILITY VALIDATION
    # ========================================================================
    # If User has wheelchair=True and Activity has accessible=False, block it
    
    user_medical_flags = user.medical_flags or {}
    requires_wheelchair = user_medical_flags.get('wheelchair', False)
    
    if requires_wheelchair and not activity.is_accessible():
        raise BookingError(
            "This activity is not wheelchair accessible. Please contact staff for assistance.",
            "ACCESSIBILITY_MISMATCH"
        )
    
    # ========================================================================
    # ALL CHECKS PASSED - CREATE BOOKING
    # ========================================================================
    
    new_booking = Booking(
        user_id=user_id,
        activity_id=activity_id,
        status=BookingStatus.CONFIRMED,
        created_at=datetime.utcnow()
    )
    
    session.add(new_booking)
    session.commit()
    session.refresh(new_booking)
    
    # Calculate remaining tokens after this booking
    if user.role != UserRole.VOLUNTEER:
        start_of_week, end_of_week = get_week_start_end()
        updated_weekly_count = session.query(Booking).filter(
            Booking.user_id == user_id,
            Booking.status == BookingStatus.CONFIRMED,
            Booking.created_at >= start_of_week,
            Booking.created_at < end_of_week
        ).count()
        
        token_limit = user.get_weekly_token_limit()
        remaining_tokens = max(0, token_limit - updated_weekly_count) if token_limit != float('inf') else 'Unlimited'
    else:
        remaining_tokens = 'N/A (Volunteer)'
    
    return {
        "success": True,
        "booking_id": new_booking.id,
        "message": "Booking confirmed successfully",
        "details": {
            "user_name": user.name,
            "activity_title": activity.title,
            "activity_start": activity.start_time.isoformat(),
            "tokens_remaining": remaining_tokens,
            "booking_status": new_booking.status.value
        }
    }


def get_user_token_balance(session: Session, user_id: int):
    """
    Calculate user's current token balance for the week
    
    Returns:
        dict: Token balance information
    """
    user = session.query(User).filter(User.id == user_id).first()
    if not user:
        raise BookingError("User not found", "USER_NOT_FOUND")
    
    if user.role == UserRole.VOLUNTEER:
        return {
            "user_id": user_id,
            "user_name": user.name,
            "membership_tier": user.membership_tier.value,
            "tokens_total": "N/A",
            "tokens_used": "N/A",
            "tokens_remaining": "N/A (Volunteer)",
            "role": user.role.value
        }
    
    start_of_week, end_of_week = get_week_start_end()
    
    # Count confirmed bookings this week
    weekly_bookings_count = session.query(Booking).filter(
        Booking.user_id == user_id,
        Booking.status == BookingStatus.CONFIRMED,
        Booking.created_at >= start_of_week,
        Booking.created_at < end_of_week
    ).count()
    
    token_limit = user.get_weekly_token_limit()
    
    if token_limit == float('inf'):
        tokens_remaining = 'Unlimited'
        tokens_total = 'Unlimited'
    else:
        tokens_remaining = max(0, token_limit - weekly_bookings_count)
        tokens_total = token_limit
    
    return {
        "user_id": user_id,
        "user_name": user.name,
        "membership_tier": user.membership_tier.value,
        "tokens_total": tokens_total,
        "tokens_used": weekly_bookings_count,
        "tokens_remaining": tokens_remaining,
        "role": user.role.value
    }


def cancel_booking(session: Session, booking_id: int, user_id: int):
    """
    Cancel a booking and free up the token
    
    Args:
        session: SQLAlchemy database session
        booking_id: ID of the booking to cancel
        user_id: ID of the user (for authorization)
        
    Returns:
        dict: Cancellation confirmation
    """
    booking = session.query(Booking).filter(
        Booking.id == booking_id,
        Booking.user_id == user_id
    ).first()
    
    if not booking:
        raise BookingError("Booking not found or unauthorized", "BOOKING_NOT_FOUND")
    
    if booking.status == BookingStatus.CANCELLED:
        raise BookingError("Booking already cancelled", "ALREADY_CANCELLED")
    
    booking.status = BookingStatus.CANCELLED
    booking.updated_at = datetime.utcnow()
    session.commit()
    
    return {
        "success": True,
        "message": "Booking cancelled successfully",
        "booking_id": booking_id
    }
