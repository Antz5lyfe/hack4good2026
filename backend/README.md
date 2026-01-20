# CareConnect Backend

Python Flask backend for the CareConnect platform implementing the "Dynamic Token" booking system.

## Features

- **Dynamic Token System**: Membership tier-based weekly token limits
- **Three-Tier Validation**: Membership, Capacity, and Medical accessibility checks
- **Volunteer Capacity Multiplier**: Volunteers increase activity capacity (base + volunteers × 2)
- **RESTful API**: Clean JSON responses with specific error codes

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

The API will start on `http://localhost:5000`

## Database

- SQLite database (`careconnect.db`) created automatically on first run
- Test data seeded with 6 users and 4 activities

## API Endpoints

### Booking
- `POST /api/book` - Create a booking with token validation
  ```json
  {
    "user_id": 1,
    "activity_id": 1
  }
  ```

### Users
- `GET /api/users` - List all users
- `GET /api/user/<id>/tokens` - Get user's token balance

### Activities
- `GET /api/activities` - List all activities with capacity info
- `GET /api/activities/<id>` - Get activity details
- `POST /api/activities` - Create new activity

### Cancellation
- `POST /api/booking/<id>/cancel` - Cancel a booking

## Test Users

1. **Alice Tan** (Weekly_1) - 1 token per week
2. **Bob Chen** (Weekly_2, Wheelchair) - 2 tokens per week
3. **Carol Lim** (Unlimited) - Unlimited tokens
4. **David Ng** (Ad-hoc) - Requires payment
5. **Emma Wong** (Volunteer) - No tokens needed
6. **Frank Lee** (Staff) - Unlimited access

## Error Codes

- `TOKEN_LIMIT_REACHED` - User exceeded weekly token limit
- `ACTIVITY_FULL` - Activity at capacity
- `ACCESSIBILITY_MISMATCH` - Wheelchair user booking non-accessible activity
- `PAYMENT_REQUIRED` - Ad-hoc member needs payment
- `VOLUNTEER_SLOTS_FULL` - All volunteer positions filled
