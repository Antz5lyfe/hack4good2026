# Product Requirements Document (PRD): CareConnect for MINDS

**Version:** 1.0  
**Status:** Draft  
**Target Event:** Hack4Good Hackathon  
**Tech Stack:** Python (Flask/FastAPI), React.js, PostgreSQL/SQLite

---

## 1. Executive Summary
**Problem:** MINDS staff spend excessive time manually consolidating registration data across disparate channels (WhatsApp, paper, email). Participants (PWIDs) and caregivers face friction in signing up for activities due to complex forms and lack of real-time availability visibility.

**Solution:** "CareConnect" is a centralized, accessibility-first web platform. It utilizes a **"Dynamic Token" logic** to manage membership entitlements automatically, provides a **unified calendar** for all users, and automates administrative rostering to reduce staff workload to under 4 hours/week.

---

## 2. User Personas & Core Needs

| Persona | Role | Key Pain Point | Ideal Outcome |
| :--- | :--- | :--- | :--- |
| **The Participant** | Beneficiary (PWID) | Confusion over which activities they are allowed to join. | "I want to see a calendar, click one button, and know I am booked." |
| **The Caregiver** | Primary Carer | Managing schedules for multiple dependents; worrying about safety. | "I want to filter events by 'Wheelchair Accessible' and book for my dad instantly." |
| **The Staff** | Admin / Coordinator | Manually checking Excel sheets vs. WhatsApp messages; dealing with overbooking. | "I want the system to stop people from booking if the class is full." |
| **The Volunteer** | Support | Hard to find where help is needed. | "I want to see empty volunteer slots and sign up without waiting for approval." |

---

## 3. Functional Requirements

### 3.1. The "Dynamic Token" Booking System (Core Logic)
The system must enforce membership tiers via a token economy rather than open booking.
* **Logic:**
    * **Ad-hoc Member:** 0 Weekly Tokens. (Must pay per booking or uses "Pay-As-You-Go" logic).
    * **Standard Member (1x):** 1 Weekly Token.
    * **Active Member (2x):** 2 Weekly Tokens.
    * **Premium Member:** Unlimited Tokens.
* **Behavior:**
    * When a user loads the app, the backend calculates `(Total Tokens Allowed - Bookings This Week)`.
    * If Balance > 0: "Sign Up" button is Active.
    * If Balance = 0: "Sign Up" button is Disabled (with tooltip: "Weekly limit reached").
    * **Ad-hoc Exception:** If Ad-hoc, the button redirects to a Payment Gateway simulation.

### 3.2. Unified Calendar & Accessibility
* **Single View:** All activities (Yoga, Arts, Training) appear on one master calendar.
* **Smart Filtering (The "Nuance" Check):**
    * If a user has `wheelchair_user = True` in their profile, activities tagged `accessible = False` are automatically hidden or greyed out.
    * Caregivers can toggle between "My Schedule" and "My Dependent's Schedule".

### 3.3. Staff Automation Dashboard
* **Input:** Staff creates an event once.
* **Output 1 (Public):** Updates the website calendar immediately.
* **Output 2 (Roster):** Auto-generates a tabular view of attendees.
* **Output 3 (Dissemination):** A "Broadcast" button that sends a WhatsApp summary to registered users (via API mock) 24 hours before the event.

### 3.4. Volunteer Integration
* **Capacity Logic:** Volunteers are treated as "Capacity Multipliers."
    * *Base Capacity:* 10 Participants.
    * *Rule:* If 1 Volunteer joins, Capacity -> 12.
* **Volunteer View:** They see the same calendar but with "Support" buttons instead of "Join."

---

## 4. Technical Architecture

### 4.1. Database Schema (ERD Concept)

**User Table**
* `id`: UUID
* `name`: String
* `role`: Enum (Participant, Caregiver, Staff, Volunteer)
* `membership_tier`: Enum (Adhoc, Weekly_1, Weekly_2, Unlimited)
* `medical_flags`: JSON (e.g., `{"wheelchair": true, "seizure_risk": false}`)
* `linked_account_id`: UUID (For caregivers managing dependents)

**Activity Table**
* `id`: UUID
* `title`: String
* `start_time`: DateTime
* `location`: String
* `base_capacity`: Integer
* `volunteer_slots`: Integer
* `requirements`: JSON (e.g., `{"accessible": true, "payment_required": false}`)

**Booking Table**
* `id`: UUID
* `user_id`: ForeignKey
* `activity_id`: ForeignKey
* `status`: Enum (Confirmed, Waitlist, Cancelled)
* `created_at`: DateTime

### 4.2. API Endpoints (REST)

**Auth & User**
* `POST /auth/login` -> Returns Token + User Role.
* `GET /user/allowance` -> Returns `{ "tokens_total": 2, "tokens_used": 1, "remaining": 1 }`.

**Activities**
* `GET /activities` -> Returns list (filtered by user access settings).
* `POST /activities` -> (Staff only) Create new event.

**Booking Transaction**
* `POST /booking/create`
    * **Input:** `{ activity_id, user_id }`
    * **Backend Validation Steps:**
        1.  Check if `Activity.current_attendees < Activity.capacity`.
        2.  Check if `User.tokens_remaining > 0` (unless Ad-hoc).
        3.  Check if `Activity.requirements` match `User.medical_flags`.
    * **Response:** `200 OK` or `400 Error` (with specific reason: "Class Full" or "Limit Reached").

---

## 5. UI/UX Guidelines
* **Font Size:** Minimum 16px body text.
* **Touch Targets:** Minimum 44px (for motor impairment accessibility).
* **Status Indicators:** Use Icons + Colors + Text (e.g., A Green Checkmark AND the word "Confirmed").
* **Zero-State:** If no classes are booked, show a friendly prompt: "Ready to have fun? Pick an activity below."

---

## 6. Implementation Prompts (For AI Assistant)

*Use the following prompts to kickstart development in Claude/ChatGPT:*

**Prompt 1 (Backend Setup):**
> "Act as a Senior Python Developer. Create a Flask application structure for the 'CareConnect' app. Set up the SQLAlchemy models based on the Schema defined in Section 4.1 of the PRD. Ensure the `User` model includes the `membership_tier` Logic."

**Prompt 2 (The Booking Logic):**
> "Write the `POST /booking/create` endpoint logic. It must strictly enforce the Token System: Query the user's bookings for the current week, compare it against their tier limit, and reject the request if they have exceeded it. Also handle the race condition where two people book the last slot simultaneously."

**Prompt 3 (Frontend Calendar):**
> "Create a React component named `UnifiedCalendar`. It should fetch data from `/activities`. If the user is a Participant, render a 'Join' button. If the user is a Volunteer, render a 'Support' button. If the user has 0 tokens left, disable the button and show a tool-tip."