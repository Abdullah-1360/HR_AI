FROM python:3.13-slim
WORKDIR /app
RUN pip install uv
COPY pyproject.toml ./
RUN uv lock && uv sync
COPY . .
EXPOSE 3005
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "3005"]
