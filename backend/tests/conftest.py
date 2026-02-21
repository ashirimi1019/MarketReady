import os

os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("AI_ENABLED", "false")
os.environ.setdefault("AI_STRICT_MODE", "false")
