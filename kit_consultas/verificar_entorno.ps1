# Verifica lo basico para usar el kit. Ejecutar con:
#   powershell -ExecutionPolicy Bypass -File verificar_entorno.ps1
# No instala nada: solo dice que falta y donde conseguirlo.
$script:ok = $true
$script:pyOk = $false

function Revisar($nombre, $comando, $argumento, $obligatorio, $ayuda) {
    $salida = ""
    $funciona = $false
    if (Get-Command $comando -ErrorAction SilentlyContinue) {
        $todo = ""
        try { $todo = (& $comando $argumento 2>&1 | Out-String) } catch { $todo = "" }
        $codigo = $LASTEXITCODE   # se guarda antes de tocar nada mas
        $salida = (($todo -split "`r?`n" | Where-Object { $_.Trim() } | Select-Object -First 1) + "").Trim()
        # En Windows, "python" puede ser un acceso directo a la Microsoft Store que no es Python real:
        # solo cuenta si termina bien y muestra un numero de version.
        if ($codigo -eq 0 -and $salida -match '\d+\.\d+') { $funciona = $true }
    }
    if ($funciona) {
        Write-Host ("[OK]       {0,-12} {1}" -f $nombre, $salida)
        return $true
    } elseif ($obligatorio) {
        Write-Host ("[FALTA]    {0,-12} {1}" -f $nombre, $ayuda); $script:ok = $false
    } else {
        Write-Host ("[opcional] {0,-12} {1}" -f $nombre, $ayuda)
    }
    return $false
}

Write-Host "== Herramientas =="
$script:pyOk = Revisar "Python"  "python" "--version" $true  "Instala Python 3.9+ desde https://www.python.org/downloads/ (marca 'Add python.exe to PATH'). Si Windows te manda a la Microsoft Store, instalalo desde python.org"
[void](Revisar "pip"     "pip"    "--version" $true  "Viene con Python; reinstala Python marcando pip")
[void](Revisar "Git"     "git"    "--version" $false "No es necesario para usar el kit (solo si algun dia lo subes a un repositorio): https://git-scm.com/download/win")
[void](Revisar "Claude Code" "claude" "--version" $true "Instala Claude Code: https://docs.claude.com/en/docs/claude-code/setup")
[void](Revisar "Node.js" "node"   "--version" $false "Solo hace falta si instalas Claude Code con npm o haces paginas con Node")

Write-Host ""
Write-Host "== Libreria de Python =="
if ($script:pyOk) {
    & python -c "import requests; print('[OK]       requests', requests.__version__)" 2>$null
    if ($LASTEXITCODE -ne 0) { Write-Host "[FALTA]    requests     Ejecuta: pip install -r requirements.txt"; $script:ok = $false }
} else {
    Write-Host "[PENDIENTE] requests    Se revisa cuando Python este instalado (luego: pip install -r requirements.txt)"
}

Write-Host ""
Write-Host "== Credenciales de Marfeel =="
$aqui = Split-Path -Parent $MyInvocation.MyCommand.Path
if ((Test-Path (Join-Path $aqui "credenciales.md")) -or ($env:MARFEEL_EMAIL -and $env:MARFEEL_PASSWORD)) {
    Write-Host "[OK]       credenciales encontradas"
} else {
    Write-Host "[FALTA]    credenciales Copia credenciales.ejemplo.md a credenciales.md y escribe tu correo y contrasena de Marfeel"
    $script:ok = $false
}

Write-Host ""
if ($script:ok) { Write-Host "Todo listo. Abre Claude Code en esta carpeta y pidele que lea CLAUDE.md." }
else            { Write-Host "Hay cosas por resolver (arriba). Vuelve a ejecutar este script al terminar." }
