We use uv as package manager for Python projects, so we need to install the required packages using uv.

```bash
uv add google-adk-python
```

# General rules
1. Follow fastapi controller and service structure
2. do not write tests, we will write them later
3. Use uv as package manager for Python projects
4. Use `uv add` to install packages
5. Use `uv run` to run the application
6. Use `fastapi run` to serve your FastAPI 
7. Always write functions from top to bottom lazilly, which means if you have a function that calls another function, write the calling function first, then if it is not used yet, add a raise an UnimplementedError
8. May use dummy response for functions that needs external API calls, put a comment `# TODO: implement this` in the function body
9. Use Angular for frontend development
10. Use FastAPI for backend development
11. Use Google ADK for agent development
12. If you need to find documentation, use Context7 mcp server especially for Google ADK, FastAPI, and Angular


# Tsak rules
1. Follow the task structure provided in the task description
2. Always update the task status in the task description
3. When completed a task, mark it as done in the task description with concise, useful comments for the next tasks/developers to begin. But prioritize inline comments over task comments.
4. Always ask question to better understand the task
5. Make the implementation as simple as possible and only as told.
6. Do stuff in feature based, starting from the frontend, then backend (endpoint). Agent development is done at another branch, so just put TODO: add agent
7. Pause after each task to be reviewed by the team lead

# Setup rules
1. Database is already set up, so no need to set up database


## FastAPI rules
1. Use dependency injection for services
<example>
    insight_service: InsightService = Depends(InsightService),
</example>
2. Use `httpx` for HTTP requests
3. Use `pydantic` for data validation
4. When encounter with google adk, gemini, or any other agent development, use mcp server to find the documentation


## Angular rules
1. Use RxJS for state management
