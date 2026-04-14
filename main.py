import os
os.environ.setdefault("OPENAI_API_KEY", "dummy_startup_key")
os.environ.setdefault("REPL_ID", "local_development")
from app import app
import routes  # noqa: F401

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
