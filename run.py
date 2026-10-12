"""Point d'entrée : python run.py  (écoute uniquement sur 127.0.0.1 par défaut)."""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    debug = os.environ.get("JOBPILOT_DEBUG", "0") == "1"
    app.run(host=app.config["HOST"], port=app.config["PORT"], debug=debug)
