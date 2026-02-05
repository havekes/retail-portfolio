# retail-portfolio
A portfolio tracker designed for the retail investor

## Contribution guidelines

Read the [AGENTS.md](./AGENTS.md) file for an overview of the architecture.

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
