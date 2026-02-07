# Parsing Agent

Telegram Parsing Agent provides stateless parsing of messages from Telegram channels.
It exposes a core async parsing function and a FastAPI endpoint.

## Development

Install dependencies:

```bash
pip install -e .
```

Run the API server:

```bash
uvicorn parsing_agent.server:app --reload
```
