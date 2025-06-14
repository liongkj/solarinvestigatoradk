.PHONY: help dev-frontend dev-backend dev

help:
	@echo "Available commands:"
	@echo "  make dev-frontend    - Starts the frontend development server (Vite)"
	@echo "  make dev-backend     - Starts the backend development server (Uvicorn with reload)"
	@echo "  make dev             - Starts both frontend and backend development servers"

dev-frontend:
	@echo "Starting frontend development server..."
	@cd frontend && npm run dev

dev-backend:
	@echo "Starting backend development server..."
	cd backend && .venv/bin/langgraph dev

# Alternative method using bash -c for environment activation
dev-backend-alt:
	@echo "Starting backend development server with activated environment..."
	cd backend && bash -c "source .venv/bin/activate && langgraph dev"

# Alternative method using uv (if you're using uv)
dev-backend-uv:
	@echo "Starting backend development server with uv..."
	cd backend && uv run langgraph dev

# Run frontend and backend concurrently
dev:
	@echo "Starting both frontend and backend development servers..."
	@make dev-frontend & make dev-backend 