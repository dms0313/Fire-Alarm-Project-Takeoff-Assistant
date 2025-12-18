This is a Python web app that analyzes construction bid documents using Gemini API to extract fire alarm scope and details from a complete construction project document set, with an optional Roboflow-powered CV feature to detect, count, and annotate fire alarm symbols using a custom-trained YOLO model.


## Secure deployment

When hosting the app on the internet, set the following environment variables to enable the built-in password gate:

- `ADMIN_PASSWORD_HASH`: A Werkzeug-compatible password hash (preferred). Generate with `python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('"'"'your-strong-password'"'"'))"`.
- `ADMIN_PASSWORD`: Convenience option for local testing—set this to a strong password and the app will derive `ADMIN_PASSWORD_HASH` at startup. Do **not** store this in production; only keep the hash.
- `SECRET_KEY`: A strong, random secret used for Flask sessions.
- `REQUIRE_LOGIN`: Defaults to `true`; keep enabled to protect every page and API endpoint.
- `SESSION_COOKIE_SECURE`: Defaults to `true` on Vercel (via the `VERCEL` env flag) but `false` for local HTTP testing. Enable it anywhere you serve the app over HTTPS.

You can also set `SESSION_LIFETIME_MINUTES` to control how long sessions stay active (default: 240 minutes).

### How to log in

1. Set either `ADMIN_PASSWORD_HASH` (preferred) **or** `ADMIN_PASSWORD` before starting the app. There is no default password—your login password is whatever value you configure in these environment variables.
2. Visit `/login` (automatically shown when `REQUIRE_LOGIN=true`).
3. Enter the password you configured in step 1. The app verifies it against `ADMIN_PASSWORD_HASH`, so the password only works if you supplied one of the environment variables above.

## Deploying on Vercel

The repository includes a Vercel entrypoint (`api/index.py`) and configuration (`vercel.json`) so you can deploy the Flask app as a serverless function.

1. Install the Vercel CLI and log in: `npm i -g vercel && vercel login`.
2. Set the required environment variables in the Vercel dashboard or via CLI:
   - `ADMIN_PASSWORD_HASH` (required when `REQUIRE_LOGIN=true`)
   - `SECRET_KEY`
   - `GEMINI_API_KEY` or `GOOGLE_API_KEY` (for Gemini features)
   - Optional: `SESSION_LIFETIME_MINUTES`, `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_SAMESITE`
3. Deploy from the project root: `vercel --prod`.

Notes:
- The `vercel.json` routes all traffic to the Flask WSGI app exposed in `api/index.py` using the `@vercel/python@3.11.0` runtime declaration.
- Local YOLO model inference is typically unavailable in serverless environments; the app will run with Gemini-only analysis unless you provide a lightweight model file via storage and point `LOCAL_MODEL_PATH` to it.
