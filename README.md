This is a Python web app that analyzes construction bid documents using Gemini API to extract fire alarm scope and details from a complete construction project document set, with an optional Roboflow-powered CV feature to detect, count, and annotate fire alarm symbols using a custom-trained YOLO model.


## Secure deployment

When hosting the app on the internet, set the following environment variables to enable the built-in password gate:

- `ADMIN_PASSWORD_HASH`: A Werkzeug-compatible password hash (preferred). Generate with `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('"'"'your-strong-password'"'"'))"`.
- `SECRET_KEY`: A strong, random secret used for Flask sessions.
- `REQUIRE_LOGIN`: Defaults to `true`; keep enabled to protect every page and API endpoint.
- `SESSION_COOKIE_SECURE`: Defaults to `true` to require HTTPS for session cookies; disable only for local HTTP testing.

You can also set `SESSION_LIFETIME_MINUTES` to control how long sessions stay active (default: 240 minutes).
