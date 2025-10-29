# retail-portfolio
A portfolio tracker designed for the retail investor

## Development

### Prerequisites

- Python 3.14 or higher
- uv package manager
- Docker and Docker Compose (for running with containers)

### Running the app

- Using Docker compose is the preferred way to run the application.
- The app will be available at `http://127.0.0.1:8000`.
- Test the ping endpoint at `http://127.0.0.1:8000/api/ping` (returns `{"ping": "pong"}`).
- Interactive API documentation at `http://127.0.0.1:8000/docs`.

### During development

- `source .venv/bin/activate` to activate the virtual environment
- Run tests: `uv run pytest`
- Lint code: `uv run pylint main.py`
