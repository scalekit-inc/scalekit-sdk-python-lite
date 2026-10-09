"""Configuration for the sample, read from environment variables or a ``.env`` file."""

import os
import secrets
import sys


def _load_env_file(path):
    try:
        with open(path) as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                key, _, value = line.partition("=")
                key, value = key.strip(), value.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = value
    except IOError:
        pass


def load_settings():
    here = os.path.dirname(os.path.abspath(__file__))
    _load_env_file(os.path.join(here, ".env"))

    missing = [k for k in ("SCALEKIT_ENVIRONMENT_URL", "SCALEKIT_CLIENT_ID", "SCALEKIT_CLIENT_SECRET")
               if not os.environ.get(k)]
    if missing:
        sys.exit("Missing {} — copy .env.example to .env and fill it in.".format(", ".join(missing)))

    port = int(os.environ.get("PORT", "8080"))
    base_url = os.environ.get("APP_BASE_URL", "http://localhost:{}".format(port)).rstrip("/")
    return {
        "env_url": os.environ["SCALEKIT_ENVIRONMENT_URL"].rstrip("/"),
        # The `iss` claim of the tokens Scalekit issues; the environment URL unless told otherwise.
        "issuer": (os.environ.get("SCALEKIT_ISSUER") or os.environ["SCALEKIT_ENVIRONMENT_URL"]).rstrip("/"),
        "client_id": os.environ["SCALEKIT_CLIENT_ID"],
        "client_secret": os.environ["SCALEKIT_CLIENT_SECRET"],
        "port": port,
        "redirect_uri": base_url + "/callback",
        "post_logout_redirect_uri": base_url + "/",
        # A fixed secret keeps sessions across restarts; a random one is fine for a demo.
        "session_secret": os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32),
    }
