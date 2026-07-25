# VV Residency Hotel Management API

Production-ready FastAPI backend for the VV Residency Hotel Management & Booking platform.

## Tech Stack

- **Framework**: FastAPI 0.111+
- **Database**: MongoDB with Motor async driver
- **Authentication**: JWT (access + refresh tokens) with bcrypt password hashing
- **Validation**: Pydantic V2
- **Python**: 3.10+

## Project Structure

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI app, lifespan, middleware, seed data
│   ├── auth/
│   │   ├── __init__.py
│   │   └── dependencies.py      # get_current_user, require_roles
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py          # Environment-based settings
│   ├── core/
│   │   ├── __init__.py
│   │   └── exceptions.py        # Custom exception classes + handlers
│   ├── database/
│   │   ├── __init__.py          # Re-export shim
│   │   └── mongodb.py           # Motor connection, collections, indexes
│   ├── middleware/
│   │   ├── __init__.py
│   │   └── logging.py           # Request/response logging
│   ├── models/
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── room.py
│   │   └── booking.py
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── auth.py              # Token schemas
│   │   ├── user.py              # User request/response schemas
│   │   ├── room.py              # Room request/response schemas
│   │   └── booking.py           # Booking request/response schemas
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py              # /api/auth/*
│   │   ├── rooms.py             # /api/rooms/*
│   │   ├── bookings.py          # /api/bookings/*
│   │   └── dashboard.py         # /api/dashboard/*
│   ├── services/
│   │   ├── __init__.py
│   │   ├── auth_service.py      # Auth business logic
│   │   ├── room_service.py      # Room CRUD business logic
│   │   ├── booking_service.py   # Booking business logic
│   │   └── dashboard_service.py # Dashboard aggregation
│   └── utils/
│       ├── __init__.py
│       └── security.py          # JWT + bcrypt utilities
├── requirements.txt
├── .env
├── .env.example
└── README.md
```

## Quick Start

### Prerequisites

- Python 3.10+
- MongoDB (local or Atlas)

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and update values:

```bash
cp .env.example .env
```

Edit `.env`:

```env
# Server settings
PORT=8000
HOST=0.0.0.0

# Database settings
MONGODB_URL=mongodb://localhost:27017
DATABASE_NAME=vvresidency

# Security settings (generate with: openssl rand -hex 32)
JWT_SECRET=your_jwt_secret_key_here
JWT_REFRESH_SECRET=your_jwt_refresh_secret_key_here
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7
```

### 3. Start MongoDB

```bash
# Local MongoDB
mongod

# Or use Docker
docker run -d -p 27017:27017 --name vvresidency-mongo mongo:7
```

### 4. Run the Server

```bash
# Development (with hot reload)
uvicorn app.main:app --reload --port 8000

# Production
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
```

### 5. Verify

- API Docs: http://hotelmanagement-duem.onrender.com/docs
- Health Check: http://hotelmanagement-duem.onrender.com/health
- Frontend: Open `index.html` in a browser (or serve it)

## Default Credentials

The database is seeded with a default administrator on first run:

| Email | Password | Role |
|---|---|---|
| admin@vvresidency.com | admin123 | admin |

> ⚠️ **Change these credentials in production!**

## API Endpoints

### Authentication (`/api/auth`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | No | Register new staff user |
| POST | `/api/auth/login` | No | Login, receive JWT tokens |
| POST | `/api/auth/refresh` | No | Refresh access token |
| GET | `/api/auth/me` | Yes | Get current user profile |

### Rooms (`/api/rooms`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/rooms` | No | List all rooms |
| GET | `/api/rooms/search` | No | Search available rooms by dates |
| GET | `/api/rooms/{id}` | No | Get single room |
| POST | `/api/rooms` | Yes | Create room (admin/staff) |
| PUT | `/api/rooms/{id}` | Yes | Update room (admin/staff) |
| PATCH | `/api/rooms/{id}/status` | Yes | Update room status (admin/staff) |
| DELETE | `/api/rooms/{id}` | Yes | Delete room (admin/staff) |

### Bookings (`/api/bookings`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/bookings` | Yes | List all bookings (admin/staff) |
| GET | `/api/bookings/{id}` | Yes | Get single booking (admin/staff) |
| POST | `/api/bookings` | No | Create booking (public) |
| PATCH | `/api/bookings/{id}/status` | Yes | Update status (admin/staff) |
| DELETE | `/api/bookings/{id}` | Yes | Cancel & delete booking (admin/staff) |

### Dashboard (`/api/dashboard`)

| Method | Endpoint | Auth | Description |
|---|---|---|---|
| GET | `/api/dashboard/stats` | No | Get dashboard metrics & recent bookings |

## MongoDB Collections

### `users`
| Field | Type | Index |
|---|---|---|
| email | string | unique |
| hashed_password | string | — |
| role | string | — |
| name | string | — |
| created_at | datetime | — |

### `rooms`
| Field | Type | Index |
|---|---|---|
| id | string | unique |
| name | string | — |
| type | string | index |
| price | float | — |
| status | string | index |
| cls | string | — |
| feats | array[string] | — |
| fcls | array[string] | — |

### `bookings`
| Field | Type | Index |
|---|---|---|
| booking_id | string | unique |
| guest_name | string | — |
| guest_email | string | index |
| guest_phone | string | — |
| room_id | string | index |
| room_name | string | — |
| checkin | string | compound |
| checkout | string | compound |
| amount | float | — |
| guests_count | int | — |
| special_requests | string | — |
| status | string | index |

## Security

- **Password Hashing**: bcrypt with auto-generated salt
- **JWT Access Tokens**: 30-minute expiry (configurable)
- **JWT Refresh Tokens**: 7-day expiry (configurable)
- **RBAC**: `admin` and `staff` roles
- **CORS**: Configured for development (restrict in production)
- **Input Validation**: Pydantic V2 with regex, min/max constraints
- **Request Logging**: All requests logged with method, path, status, and duration

## Production Deployment

### Environment Checklist

1. Generate new JWT secrets: `openssl rand -hex 32`
2. Set `MONGODB_URL` to your production MongoDB URI
3. Restrict CORS `allow_origins` to your frontend domain
4. Use `--workers 4` (or more) with uvicorn
5. Change default admin password
6. Set up MongoDB authentication
7. Enable HTTPS (via reverse proxy like Nginx)

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

## License

Private — VV Residency Hotels © 2025
