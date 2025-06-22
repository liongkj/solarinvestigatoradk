.PHONY: help dev-frontend dev-backend dev docker-build docker-dev docker-down docker-logs

help:
	@echo "Available commands:"
	@echo "  make dev-frontend    - Starts the frontend development server (Angular)"
	@echo "  make dev-backend     - Starts the backend development server (FastAPI)"
	@echo "  make dev             - Starts both frontend and backend development servers"
	@echo ""
	@echo "Docker commands:"
	@echo "  make docker-build    - Build all Docker services"
	@echo "  make docker-dev      - Start all services in development mode with Docker"
	@echo "  make docker-down     - Stop all Docker services"
	@echo "  make docker-logs     - View logs from all services"

dev-frontend:
	@echo "Starting frontend development server..."
	@cd frontend && npm run start

dev-backend:
	@echo "Starting backend development server..."
	cd backend && uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# Run frontend and backend concurrently
dev:
	@echo "Starting both frontend and backend development servers..."
	@make dev-frontend & make dev-backend

# Docker commands
docker-build:
	@echo "Building all Docker services..."
	@docker-compose build

docker-dev:
	@echo "Starting all services in development mode with Docker..."
	@docker-compose -f docker-compose.yml -f docker-compose.dev.yml up --build

docker-down:
	@echo "Stopping all Docker services..."
	@docker-compose down

docker-logs:
	@echo "Viewing logs from all services..."
	@docker-compose logs -f 