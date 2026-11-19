# Kit para consultar Marfeel con Claude

Sirve para sacar páginas vistas, usuarios únicos y fuentes de tráfico de una URL o una lista de URL de El Universal, con filtros.

## 1. Verifica lo básico

En PowerShell, dentro de esta carpeta:

```
powershell -ExecutionPolicy Bypass -File verificar_entorno.ps1
```

Revisa que estén instalados:

| Herramienta | Obligatoria | Dónde |
|---|---|---|
| Python 3.9 o superior (con `pip` y en el PATH) | Sí | https://www.python.org/downloads/ |
| Claude Code | Sí | https://docs.claude.com/en/docs/claude-code/setup |
| Node.js y Git | No (opcionales; el kit no los usa) | https://nodejs.org · https://git-scm.com/download/win |

Después instala la librería: `pip install -r requirements.txt`

## 2. Credenciales

1. Copia `credenciales.ejemplo.md` como `credenciales.md`.
2. Escribe **tu** correo y contraseña de Marfeel (mejor un usuario con rol API).
3. No lo compartas ni lo subas a ningún sitio.

Marfeel limita la cuenta a **1 petición por minuto**, compartida por todos los que la usan. Si otra persona está descargando datos con la misma cuenta, las consultas esperarán o fallarán con 429.

## 3. Usa Claude

Abre Claude Code en esta carpeta (`claude`). Claude leerá `CLAUDE.md` solo. Ejemplos de lo que puedes pedirle:

- "Dame páginas vistas y usuarios únicos de estas URL: …"
- "Compara la semana del 2 al 8 de noviembre con la anterior para el periodista 52k8j5v7_spo."
- "Agrupa por sección y compara con el mes pasado."
- "Lo mismo, pero desde el 1 de noviembre hasta ayer."
- "Desglosa por fuente de tráfico las 20 URL de `urls.txt`."
- "Compara estos artículos con el filtro del equipo de Sucesos."

Si Claude necesita una métrica o variable que no conoce, te pedirá que armes la consulta en Explore y copies el cuerpo de la petición a `consultas_prueba/` (instrucciones en `CLAUDE.md`).

O sin Claude, directo: `python consultar.py --archivo urls.txt` (más opciones con `--help`).

## Qué hay en la carpeta

| Archivo | Para qué |
|---|---|
| `CLAUDE.md` | Instrucciones y reglas de Marfeel para Claude |
| `consultar.py` | Herramienta: consulta por URL o lista, por periodista, comparación de periodos, agrupaciones, filtros, únicos sin duplicar |
| `ejecutar_consulta.py` | Ejecuta una consulta copiada de Explore (para aprender variables nuevas) |
| `periodistas.txt` | Código de cada periodista y su id de Marfeel |
| `ejemplos_explore/`, `consultas_prueba/` | Consultas de ejemplo y carpeta para las de prueba |
| `marfeel.py` | Cliente de la API (autenticación, límite, paginación) |
| `equipos.json` | Equipos de trabajo y sus ids de filtro |
| `verificar_entorno.ps1` | Comprueba Python, Claude Code, requests y credenciales |
| `.gitignore` | Evita subir credenciales, token y resultados |
