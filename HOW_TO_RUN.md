# HOW TO RUN

Run these commands from the project root. Use separate terminals where noted.

1) Backend (terminal A)

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Optional if model missing or you changed training
python ml/train.py
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

2) Website (terminal B)

```bash
cd website
python3 -m http.server 8080
# Open http://localhost:8080/index.html
```

3) Mobile app (terminal C)

```bash
cd mobile_app
npm install --legacy-peer-deps
npx expo start
# In the app Settings set API base to: http://<your-LAN-IP>:8000
```

Fallback: run the mobile web build (if Expo Go incompatible)

```bash
cd mobile_app
EXPO_OFFLINE=1 npx expo export --platform web
cd dist
python3 -m http.server 8082
# Open http://localhost:8082
```

That's it — three simple terminal sections to run backend, website, and mobile UI.
