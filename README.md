# retail-portfolio
A portfolio tracker designed for the retail investor

## Contribution guidelines

### Running the app

- Create backend `.env` by copying `.env.example`
- Create frontend `./frontend/.env` by copying `./frontend/.env.example`

Using Docker compose is the only supported way to run the application: `docker compose up -d`

- The app will be available at `http://localhost:8001`
- Test the ping endpoint at `http://localhost:8001/api/ping`
- Interactive API documentation at `http://localhost:8001/redoc`
- Frontend will be running at `http://localhost:8100/`

### During development

It is recommend to always run commands from inside the container: `docker compose exec [backend|frontend] <command>`

- Run tests: `uv run pytest`
- Check format: `uv run ruff format --check`
- Lint code: `uv run ruff check`
- Type-check code: `uv run basedpyright src`

- Run frontend format and lint `npm run lint`

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

- Raise HTTPException from within a serice (except Authorization service). Instead raise a custom exception and handle it in the router.

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
