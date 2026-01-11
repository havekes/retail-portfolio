# retail-portfolio
A portfolio tracker designed for the retail investor

## Contributing

### Prerequisites

- Python 3.14 or higher
- uv package manager
- Docker and Docker Compose (for running with containers)

### Running the app

- Create Vite `.env`
- Using Docker compose is the preferred way to run the application.
- The app will be available at `http://127.0.0.1:8001`.
- Test the ping endpoint at `http://127.0.0.1:8001/api/ping` (returns `{"ping": "pong"}`).
- Interactive API documentation at `http://127.0.0.1:8001/redoc`.

### During development

- `source .venv/bin/activate` to activate the virtual environment
- Run tests: `uv run pytest`
- Lint code: `uv run ruff check`

### Backend application structure

The following abstraction layers are used (each in their own modules):

- Routers
  - FastAPI route handlers
  - Define the route parameters, payload, return type and validation logic
  - Delegate business logic to services and/or repositories for simple crud operations
- Services
  - Business logic layer
  - Handle complex logic
  - Use repositories for data access
- Repositories
  - Data access abstraction layer
  - Abstract class defining the interface
  - Always return schemas (not models)
  - SQL Alchemy implementation
- Schemas
  - Data structure definition for all communications accross the app
  - By convention:
    - `Read` suffix for `GET` enpoints return types
    - `Write` suffix for `POST`/`PATCH` endpoints payload types
- Models
  - Reflect database structure
  - Used to generate migrations
- External
  - External API wrappers
  - Params/returns are schemas
  - Can be used as services by the app
  
Other modules:
- Config
  - Application wide typed configuration schema
- Commands
### Do's and don'ts

#### Don't

- Raise HTTPException from within a serice. Raise a custom exception and handle it in the router.

### Code snippets

#### Load local library only during dev

```python
# Force reload the ws_api module from local path during development
if settings.envrionement == "dev":
    sys.path.insert(0, "/app/modules/ws-api-python")
    for module_name in list(sys.modules.keys()):
        if module_name.startswith("ws_api"):
            del sys.modules[module_name]
```
