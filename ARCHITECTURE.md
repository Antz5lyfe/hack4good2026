graph TD
    %% -- FRONTEND LAYER --
    subgraph "Frontend Layer (React.js / Next.js)"
        User_UI[<b>Participant & Caregiver Portal</b><br/>Unified Calendar, Token Display]
        Staff_UI[<b>Staff Dashboard</b><br/>Roster Heatmaps, Auto-Reporting]
        Vol_UI[<b>Volunteer Portal</b><br/>Support Slot Signup]
    end

    %% -- API LAYER --
    subgraph "Backend API (Python Flask/FastAPI)"
        API[<b>API Gateway</b><br/>REST Endpoints]
        
        subgraph "Logic Controllers"
            Auth_Svc[<b>Auth Service</b><br/>JWT & Role Management]
            
            Booking_Logic[<b>Booking Engine</b><br/><i>The 'Token' Logic Gate</i>]
            
            Filter_Logic[<b>Nuance Filter</b><br/>Matches Medical Flags vs Activity Tags]
            
            Roster_Bot[<b>Automation Bot</b><br/>Pandas Script for Reporting]
        end
    end

    %% -- DATA LAYER --
    subgraph "Database (PostgreSQL / SQLite)"
        DB[(<b>Main Database</b><br/>Users, Activities, Bookings)]
    end

    %% -- EXTERNAL --
    subgraph "External Integrations"
        Pay[<b>Payment Mock</b><br/>(Stripe/PayNow)]
        Msg[<b>Notification API</b><br/>(Twilio/WhatsApp)]
    end

    %% -- FLOW CONNECTIONS --
    
    %% Client to API
    User_UI -->|1. Request Booking| API
    Staff_UI -->|Manage Events| API
    Vol_UI -->|Register Support| API

    %% API Routing
    API --> Auth_Svc
    API --> Booking_Logic
    API --> Roster_Bot

    %% Core Logic Flow
    Booking_Logic -->|2. Check Membership Tier| Auth_Svc
    Booking_Logic -->|3. Check Suitability| Filter_Logic
    Booking_Logic -->|4. Check Capacity| DB
    
    %% Volunteer Logic
    Vol_UI -.->|Increases Capacity| Booking_Logic

    %% Database Interactions
    Auth_Svc --> DB
    Roster_Bot -->|Fetch Data| DB
    
    %% External Actions
    Booking_Logic -->|If Ad-hoc| Pay
    Roster_Bot -->|Weekly Broadcast| Msg
    
    %% Feedback Loop
    Booking_Logic -->|5. Return Success/Fail| User_UI