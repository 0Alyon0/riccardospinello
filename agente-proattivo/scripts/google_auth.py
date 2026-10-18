"""Collega il tuo account Google (una sola volta).

1. Su https://console.cloud.google.com crea un progetto, abilita Google Calendar API e Gmail API.
2. Crea credenziali OAuth di tipo "App desktop" e scarica il JSON in data/google_client_secret.json.
3. Esegui: python -m scripts.google_auth
"""
from google_auth_oauthlib.flow import InstalledAppFlow

from app import config
from app.integrazioni.google import SCOPES


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file(str(config.GOOGLE_CLIENT_SECRET_PATH), SCOPES)
    creds = flow.run_local_server(port=0)
    config.GOOGLE_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.GOOGLE_TOKEN_PATH.write_text(creds.to_json())
    print(f"Token salvato in {config.GOOGLE_TOKEN_PATH}")


if __name__ == "__main__":
    main()
