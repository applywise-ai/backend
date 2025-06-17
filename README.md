# ApplyWise Backend

Backend service for ApplyWise job application automation platform.

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   FastAPI API   │    │  Celery Workers │    │  Browser Pool   │
│                 │    │                 │    │                 │
│ • /apply        │───▶│ • Job Processing│───▶│ • Chrome Drivers│
│ • /status       │    │ • Site Detection│    │ • Persistent    │
│ • /users/{id}/  │    │ • Form Filling  │    │ • Thread-Safe   │
│   applications  │    │ • Duplicate Check│   │ • Auto-cleanup  │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   PostgreSQL    │    │      Redis      │    │  Firebase Storage│
│                 │    │                 │    │                 │
│ • Users         │    │ • Task Queue    │    │ • Screenshots   │
│ • Applications  │    │ • Results Cache │    │ • File Storage  │
│ • Logs          │    │ • Session Data  │    │ • Public URLs   │
│ • Job Dedup     │    │                 │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## 🚀 Features

- **Fast API Server**: FastAPI with async support and automatic OpenAPI docs
- **Task Queue**: Celery with Redis for background job processing
- **Browser Pool**: Persistent Chrome drivers to avoid cold starts
- **Multi-Site Support**: LinkedIn, Indeed, Greenhouse, and generic job sites
- **Screenshot Capture**: Automatic screenshots stored in Firebase Storage
- **PostgreSQL Database**: User tables with application relationships and duplicate detection
- **Docker Ready**: Complete containerization with Docker Compose
- **Monitoring**: Celery Flower for task monitoring
- **Scalable**: Easy horizontal scaling of workers

## 📋 Prerequisites

- Python 3.11+
- Redis (installed locally or via Docker)
- Firebase project with Storage enabled
- Chrome browser installed
- Tailscale account (for database access)

## 🛠️ Quick Start

### 1. Clone and Setup

```bash
# Clone repository
git clone <repository-url>
cd applywise-backend

# Install dependencies
make install
```

### 2. Onboarding (New Developers)

For new team members, simply run:

```bash
make onboard
```

This will:
- Install Tailscale if not already installed
- Guide you through joining the Tailscale network
- Create your `.env` file with proper database configuration
- Set up all necessary environment variables

### 3. Manual Configuration (Alternative)

If you prefer manual setup, create a `.env` file in the root directory:

```bash
# Firebase
FIREBASE_CREDENTIALS_PATH=/path/to/firebase-credentials.json
FIREBASE_STORAGE_BUCKET=your-project-id.appspot.com

# PostgreSQL (use private IP when connected via Tailscale)
POSTGRES_HOST=172.31.85.170
POSTGRES_PORT=5432
POSTGRES_DB=applywise
POSTGRES_USER=postgres
POSTGRES_PASSWORD=your-password

# AWS
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# API
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=["http://localhost:3000","http://localhost:3001"]

# Environment
ENVIRONMENT=development
DEBUG=true
```

### 4. Development

Start the development environment (Redis + API server):
```bash
make dev
```

Start the Celery worker in a new terminal:
```bash
make celery
```

### 5. Available Commands

```bash
# New developer onboarding
make onboard

# Start development environment (Redis + API)
make dev

# Start Celery worker
make celery

# Run tests
make test

# View logs
make logs

# Check health
make health

# Clean up resources
make clean

# View all available commands
make help
```

### 6. Access Services

- **API**: http://localhost:8000
- **API Documentation**: http://localhost:8000/docs
- **Redis**: localhost:6379

## 🔐 Database Access

Our PostgreSQL database is hosted on AWS RDS in a private subnet. To access it:

1. **For New Developers**: Run `make onboard` - this handles everything automatically
2. **Manual Setup**: Install Tailscale and join our network to access the private database IP

The onboarding process ensures you can connect to the database securely without complex VPN setup.

## 📚 API Documentation

### Submit Job Application

```http
POST /apply
Content-Type: application/json

{
  "job_url": "https://www.linkedin.com/jobs/view/3750000000",
  "resume_data": {
    "first_name": "John",
    "last_name": "Doe",
    "email": "john.doe@example.com",
    "phone": "+1-555-123-4567",
    "linkedin": "https://linkedin.com/in/johndoe",
    "website": "https://johndoe.dev"
  },
  "cover_letter_template": "Dear Hiring Manager...",
  "application_answers": {
    "years_experience": "5",
    "willing_to_relocate": "Yes"
  }
}
```

**Response:**
```json
{
  "task_id": "uuid-string",
  "status": "queued",
  "message": "Job application queued for processing"
}
```

### Check Application Status

```http
GET /status/{task_id}
```

**Response:**
```json
{
  "task_id": "uuid-string",
  "status": "completed",
  "result": {
    "screenshot_urls": ["https://..."],
    "completed_at": "2024-01-01T12:00:00Z"
  }
}
```

### Get Applications

```http
GET /applications?skip=0&limit=100
```

### Health Check

```http
GET /health
```

## 🧪 Testing

Run the test suite to verify everything is working:

```bash
# Make test script executable
chmod +x scripts/test_api.py

# Run tests
python scripts/test_api.py
```

## 🔧 Development

### Local Development Setup

```bash
# Quick start for new developers
make onboard

# Or manual setup:
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 2. Install dependencies
make install

# 3. Set up environment (if not using onboard)
# Edit .env with your configuration

# 4. Start development environment
make dev

# 5. In another terminal, start Celery worker
make celery
```

### Project Structure

```
applywise-backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration settings
│   ├── database.py          # Database setup
│   ├── models.py            # SQLAlchemy models
│   ├── schemas.py           # Pydantic schemas
│   ├── celery_app.py        # Celery configuration
│   ├── tasks.py             # Celery tasks
│   ├── browser_pool.py      # Browser management
│   └── storage.py           # File storage utilities
├── scripts/
│   ├── start.sh             # Startup script
│   └── test_api.py          # API test suite
├── docker-compose.yml       # Docker services
├── Dockerfile              # Application container
├── requirements.txt        # Python dependencies
└── env.example            # Environment template
```

## 🎯 Supported Job Sites

The system automatically detects and handles different job sites:

- **LinkedIn**: Easy Apply jobs with multi-step forms
- **Indeed**: Direct applications and redirects
- **Greenhouse**: ATS-powered applications
- **Generic**: Fallback for other job sites

## 📊 Monitoring

### Celery Flower

Access Celery Flower at http://localhost:5555 to monitor:
- Active tasks
- Worker status
- Task history
- Performance metrics

### Application Logs

```bash
# View all logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f api
docker-compose logs -f worker
```

### Database Queries

Connect to the database via Tailscale:

```bash
# Connect to PostgreSQL (ensure Tailscale is running)
psql -h 172.31.85.170 -U postgres -d applywise
```

```sql
-- Check application status
SELECT task_id, status, job_url, created_at FROM job_applications;

-- View application logs
SELECT al.level, al.message, al.timestamp 
FROM application_logs al 
JOIN job_applications ja ON al.application_id = ja.id 
WHERE ja.task_id = 'your-task-id';
```

## 🚀 Deployment

### Docker Compose (Recommended)

```bash
# Production deployment
docker-compose -f docker-compose.yml up -d

# Scale workers
docker-compose up -d --scale worker=4
```

### Kubernetes

```yaml
# Example Kubernetes deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: applywise-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: applywise-api
  template:
    metadata:
      labels:
        app: applywise-api
    spec:
      containers:
      - name: api
        image: applywise-backend:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          value: "postgresql://..."
```

### AWS ECS

Use the provided Dockerfile with ECS task definitions for AWS deployment.

## ⚡ Performance Optimization

### Browser Pool Configuration

- **Persistent Drivers**: Browsers stay warm between tasks
- **Concurrent Workers**: Multiple workers with isolated browser sessions
- **Memory Management**: Automatic cleanup of inactive browsers
- **Resource Limits**: Configurable timeouts and limits

### Scaling Guidelines

- **API Server**: 2-4 instances behind load balancer
- **Workers**: 1-2 workers per CPU core
- **Database**: Connection pooling with 10-20 connections per worker
- **Redis**: Single instance handles 1000+ concurrent tasks

## 🔒 Security

- **Environment Variables**: Sensitive data in environment variables
- **Non-root Containers**: Docker containers run as non-root user
- **Input Validation**: Pydantic schemas validate all inputs
- **Rate Limiting**: Implement rate limiting for production use
- **CORS**: Configure CORS appropriately for your frontend

## 🐛 Troubleshooting

### Common Issues

1. **Database Connection Issues**
   ```bash
   # Ensure Tailscale is connected
   tailscale status
   
   # Test database connectivity
   nc -z -v 172.31.85.170 5432
   
   # Re-run onboarding if needed
   make onboard
   ```

2. **Chrome Driver Issues**
   ```bash
   # Update Chrome driver
   docker-compose build --no-cache worker
   ```

3. **Redis Connection**
   ```bash
   # Check Redis status
   docker-compose logs redis
   ```

4. **Worker Not Processing Tasks**
   ```bash
   # Restart workers
   docker-compose restart worker
   ```

5. **Tailscale Setup Issues**
   ```bash
   # Check if Tailscale is installed
   which tailscale
   
   # Login to Tailscale
   sudo tailscale up
   
   # Verify network access
   tailscale ping 100.121.95.26
   ```

### Debug Mode

Enable debug mode in `.env`:
```bash
DEBUG=true
HEADLESS_BROWSER=false  # See browser in action
```

## 📈 Monitoring & Metrics

### Health Endpoints

- `GET /health` - Overall system health
- `GET /workers` - Celery worker status
- `GET /` - Basic API status

### Metrics Collection

Integrate with monitoring tools:
- Prometheus metrics
- Grafana dashboards
- Application logs
- Performance monitoring

## 🤝 Contributing

### Getting Started

1. Fork the repository
2. Run `make onboard` to set up your development environment
3. Create a feature branch
4. Make your changes
5. Add tests
6. Submit a pull request

### Team Onboarding

New team members should:
1. Get added to the Tailscale network
2. Clone the repository
3. Run `make onboard` - this handles all setup automatically
4. Start developing with `make dev`

No complex VPN setup or IP whitelisting required!

## 📄 License

This project is licensed under the MIT License.

## 🆘 Support

For support and questions:
- Create an issue in the repository
- Check the troubleshooting section
- Review the API documentation at `/docs`

---

**Built with ❤️ for fast job applications**