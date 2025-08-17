.PHONY: help start stop restart build logs test clean dev install celery celery-health

# Default target
help:
	@echo "ApplyWise Backend - Available Commands:"
	@echo ""
	@echo "  make start        - Start all services with Docker Compose"
	@echo "  make stop         - Stop all services"
	@echo "  make restart      - Restart all services"
	@echo "  make build        - Build Docker images"
	@echo "  make logs         - View logs from all services"
	@echo "  make logs-live    - View live application logs (app.log)"
	@echo "  make test         - Run API tests"
	@echo "  make clean        - Clean up Docker resources"
	@echo "  make dev          - Start development environment"
	@echo "  make dev-verbose  - Start development environment with verbose logging"
	@echo "  make install      - Install Python dependencies locally"
	@echo "  make celery       - Start Celery worker"
	@echo "  make celery-health - Check Celery worker status"
	@echo "  make health       - Check overall system health via API"
	@echo "  make check-db     - Test database connectivity"
	@echo "  make onboard      - Onboard new developer with database access"
	@echo "  make jobs         - Fetch jobs from the API"
	@echo ""

# Start all services
start:
	@echo "🚀 Starting ApplyWise Backend..."
	./scripts/start.sh

# Stop all services
stop:
	@echo "🛑 Stopping all services..."
	docker-compose down

# Restart all services
restart:
	@echo "🔄 Restarting all services..."
	docker-compose restart

# Build Docker images
build:
	@echo "🔨 Building Docker images..."
	docker-compose build

# View logs
logs:
	@echo "📋 Viewing logs..."
	docker-compose logs -f

# View live application logs
logs-live:
	@echo "📋 Viewing live application logs..."
	tail -f app.log 2>/dev/null || echo "No app.log file found. Start the app first with 'make dev' or 'make dev-verbose'"

# Run tests
test:
	@echo "🧪 Running API tests..."
	python scripts/test_api.py

# Clean up Docker resources
clean:
	@echo "🧹 Cleaning up Docker resources..."
	docker-compose down -v
	docker system prune -f

# Development environment
dev:
	@echo "🔧 Starting development environment..."
	@echo "✅ Activating virtual environment..."
	@bash -c "source venv/bin/activate && echo '✅ Virtual environment activated.' && docker-compose up -d redis && echo '✅ Redis started. Starting API server on port 8000...' && uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload"

# Development environment with verbose logging
dev-verbose:
	@echo "🔧 Starting development environment with verbose logging..."
	docker-compose up -d redis
	@echo "✅ Redis started. Starting API server on port 8000 with verbose logging..."
	uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

# Install dependencies locally
install:
	@echo "📦 Installing Python dependencies..."
	pip install -r requirements.txt

# Scale workers
scale-workers:
	@echo "⚡ Scaling workers to 4 instances..."
	docker-compose up -d --scale worker=4

# Redis shell
redis-shell:
	@echo "🔴 Opening Redis shell..."
	docker-compose exec redis redis-cli

# View worker status
workers:
	@echo "👷 Checking worker status..."
	curl -s http://localhost:8000/workers | python -m json.tool

# Health check
health:
	@echo "🏥 Checking system health..."
	curl -s http://localhost:8000/health | python -m json.tool

# Start Celery worker
celery:
	@echo "🚀 Starting Celery worker..."
	@echo "✅ Activating virtual environment..."
	@bash -c "source venv/bin/activate && echo '✅ Virtual environment activated.' && celery -A app.tasks.celery_app worker --loglevel=info"

# Check Celery worker status
celery-health:
	@echo "🔄 Checking Celery worker status..."
	@echo ""
	@echo "📊 Worker Status:"
	@celery -A app.tasks.celery_app status || echo "❌ No workers found or Celery broker unreachable"
	@echo ""
	@echo "📋 Registered Tasks:"
	@celery -A app.tasks.celery_app inspect registered || echo "❌ Could not retrieve registered tasks"
	@echo ""
	@echo "⚡ Active Tasks:"
	@celery -A app.tasks.celery_app inspect active || echo "❌ Could not retrieve active tasks"
	@echo ""
	@echo "📈 Worker Stats:"
	@celery -A app.tasks.celery_app inspect stats || echo "❌ Could not retrieve worker stats"

# Database connectivity
check-db:
	@echo "🔍 Checking database connectivity..."
	python scripts/check_db_connection.py

# New developer onboarding
onboard:
	@echo "🚀 Starting developer onboarding..."
	chmod +x scripts/onboard_new_developer.sh
	./scripts/onboard_new_developer.sh 

# Fetch jobs
jobs:
	@echo "🔍 Fetching jobs..."
	@echo "✅ Activating virtual environment..."
	@bash -c "source venv/bin/activate && echo '✅ Virtual environment activated.' && python -m app.services.fetch_jobs.main"
