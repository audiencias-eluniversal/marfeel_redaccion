"""Autenticación contra Marfeel (newsroom.bi): obtiene, guarda y renueva el token."""
import json
import re
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent
CREDENCIALES_MD = BASE_DIR / "credenciales.md"
TOKEN_FILE = BASE_DIR / "token.json"
SIGNIN_URL = "https://api.newsroom.bi/api/user/signin"


def leer_credenciales():
    texto = CREDENCIALES_MD.read_text(encoding="utf-8")
    correo = re.search(r"\*\*Correo:\*\*\s*`([^`]+)`", texto)
    clave = re.search(r"\*\*Contraseña:\*\*\s*`([^`]+)`", texto)
    if not correo or not clave:
        raise RuntimeError("No pude leer correo/contraseña de credenciales.md")
    return correo.group(1), clave.group(1)


def _extraer_token(data):
    """Busca el token en la respuesta sin asumir el nombre exacto del campo."""
    if isinstance(data, dict):
        for k in ("token", "accessToken", "access_token", "jwt", "idToken"):
            if isinstance(data.get(k), str):
                return data[k]
        for v in data.values():
            t = _extraer_token(v)
            if t:
                return t
    return None


def autenticar():
    """Hace POST al signin, guarda y devuelve un token nuevo."""
    correo, clave = leer_credenciales()
    r = requests.post(SIGNIN_URL, json={"email": correo, "password": clave}, timeout=30)
    r.raise_for_status()
    token = _extraer_token(r.json())
    if not token:
        raise RuntimeError(f"El signin respondió sin token. Campos: {list(r.json())}")
    TOKEN_FILE.write_text(json.dumps({"token": token}), encoding="utf-8")
    return token


def obtener_token(forzar=False):
    """Devuelve el token guardado, o uno nuevo si no existe o forzar=True."""
    if not forzar and TOKEN_FILE.exists():
        try:
            return json.loads(TOKEN_FILE.read_text(encoding="utf-8"))["token"]
        except (ValueError, KeyError):
            pass
    return autenticar()


if __name__ == "__main__":
    t = obtener_token(forzar=True)
    print(f"OK: token obtenido y guardado en token.json (longitud {len(t)})")
