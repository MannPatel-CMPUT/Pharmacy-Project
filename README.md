# Pharmacy Workflow Automation System

A complete pharmacy workflow automation tool with a FastAPI backend and a simple web frontend for managing prescription intakes through their lifecycle.

## Features

- **Intake Management**: Create and track prescription intakes with personalized patient information
- **Drug Interaction Checking**: Automatic detection of drug interactions between new and current medications
- **Counseling Points**: Auto-generated and editable counseling points for patients
- **Pharmacist Notes**: Add and edit pharmacist notes for each intake
- **Dispense Tracking**: Track when medications are dispensed to patients
- **Workflow Automation**: Status-based workflow with validated state transitions
- **Assignment System**: Assign intakes to staff members
- **Statistics Dashboard**: Real-time statistics on intake statuses
- **Filtering**: Filter intakes by status
- **Persistent Storage**: SQLite database for data persistence

## Workflow States

The system supports the following workflow states:

1. **new** → Initial state when intake is created
2. **triage** → Under review/triage
3. **waiting_info** → Waiting for additional information
4. **ready_to_fill** → Ready to be filled
5. **filled** → Prescription has been filled
6. **dispensed** → Medication has been dispensed to patient
7. **completed** → Final state

## Key Features Explained

### Drug Interaction Checking
- Automatically checks for interactions between new medications and current medications
- Supports major and moderate severity levels
- Displays warnings prominently in the UI
- Can re-check interactions at any time

### Personalized Intake
- Patient age tracking
- Allergy information
- Current medications for interaction checking
- Custom notes

### Counseling Points
- Auto-generated based on medication types
- Includes interaction-specific warnings
- Fully editable by pharmacists
- Displayed prominently for patient counseling

### Pharmacist Notes
- Private notes for pharmacist use
- Helps track important information
- Editable at any time

## Project Structure

```
.
├── fastapi/
│   ├── myapi.py              # Main FastAPI application
│   ├── database.py           # Database models and configuration
│   ├── routers/
│   │   └── intakes.py        # API routes for intakes
│   ├── services/
│   │   └── intake_service.py # Business logic for intakes
│   └── schemas/
│       ├── intake.py         # Pydantic models for intakes
│       └── intake_actions.py # Action schemas (status update, assign)
├── frontend/
│   └── index.html            # Web application UI
├── requirements.txt          # Python dependencies
└── README.md                 # This file
```

## Setup Instructions

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

### Installation

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Start the backend server**:
   ```bash
   cd fastapi
   uvicorn myapi:app --reload --port 8000
   ```

   The API will be available at `http://localhost:8000`
   - API documentation: `http://localhost:8000/docs`
   - Health check: `http://localhost:8000/health`

3. **Open the frontend**:
   - Simply open `frontend/index.html` in your web browser
   - Or serve it using a simple HTTP server:
     ```bash
     cd frontend
     python -m http.server 8080
     ```
     Then navigate to `http://localhost:8080`

## API Endpoints

### Intakes

- `POST /intakes` - Create a new intake (automatically checks for drug interactions)
- `GET /intakes` - List all intakes (supports `?status=` and `?assigned_to=` query parameters)
- `GET /intakes/{intake_id}` - Get a specific intake
- `POST /intakes/{intake_id}/status` - Update intake status
- `POST /intakes/{intake_id}/assign` - Assign intake to a staff member
- `POST /intakes/{intake_id}/counseling` - Update counseling points
- `POST /intakes/{intake_id}/pharmacist-notes` - Update pharmacist notes
- `POST /intakes/{intake_id}/dispense` - Mark medication as dispensed
- `GET /intakes/{intake_id}/check-interactions` - Re-check drug interactions
- `GET /intakes/stats/summary` - Get statistics summary

### Health

- `GET /health` - Health check endpoint

## Usage

1. **Create an Intake**: 
   - Fill out patient information (name, age, allergies)
   - Enter new medications
   - Optionally enter current medications for interaction checking
   - System automatically checks for drug interactions and generates counseling points

2. **View Intakes**: All intakes are displayed with:
   - Drug interaction warnings (if any)
   - Auto-generated counseling points
   - Pharmacist notes
   - Current status and assignment

3. **Update Status**: Click the status transition buttons to move intakes through the workflow

4. **Dispense Medication**: When status is "filled", click "Dispense" to mark as dispensed

5. **View Details**: Click "View Details" to see full information and edit:
   - Counseling points
   - Pharmacist notes
   - Re-check drug interactions

6. **Assign Intakes**: Click "Assign" to assign an intake to a staff member

7. **Filter**: Use the status filter dropdown to view intakes by specific status

8. **Monitor**: View real-time statistics in the header dashboard

## Database

The system uses SQLite for data persistence. The database file (`pharmacy.db`) will be automatically created in the `fastapi` directory when you first run the application.

**Note**: If you have an existing database from a previous version, you may need to delete `fastapi/pharmacy.db` to use the new schema with enhanced features.

## Development

To extend the system:

- Add new workflow states in `fastapi/services/intake_service.py` (update `ALLOWED_STATUSES` and `ALLOWED_TRANSITIONS`)
- Add new API endpoints in `fastapi/routers/intakes.py`
- Customize the frontend in `frontend/index.html`

## Notes

- The database is initialized automatically on server startup
- CORS is enabled for all origins (configure appropriately for production)
- The frontend expects the API to be running on `http://localhost:8000`
