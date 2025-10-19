# Bible Search API

AI-powered Bible search API using FastAPI and OpenAI.

## Setup

### Prerequisites
- Python 3.8+
- Poetry (install from https://python-poetry.org/docs/#installation)

### Installation

1. Install dependencies:
```bash
poetry install
```

2. Activate the virtual environment:
```bash
poetry shell
```

3. Set your OpenAI API key:
```bash
export OPENAI_API_KEY="your-api-key-here"
```

### Running the API

Start the development server:
```bash
poetry run start
```

Or manually:
```bash
poetry run uvicorn search:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

### API Endpoints

- `GET /` - Health check
- `GET /search?query=<search_term>&result_count=<one|few|many>&content_type=<verses|passages|all>&model_type=<fast|advanced>` - Search for Bible passages

### Development

Run tests:
```bash
poetry run pytest
```

Format code:
```bash
poetry run black .
poetry run isort .
```

Lint code:
```bash
poetry run flake8 .
```

## Migration from Conda

This project has been migrated from conda to Poetry for better dependency management and reproducibility.
