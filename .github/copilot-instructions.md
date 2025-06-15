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


# Tsak rules
1. Follow the task structure provided in the task description
2. Always update the task status in the task description
3. When completed a task, mark it as done in the task description with concise, useful comments for the next tasks/developers to begin. But prioritize inline comments over task comments.