$ErrorActionPreference = 'Stop'

$files = @(
    Get-ChildItem -LiteralPath $PSScriptRoot -File -Filter 'WhatsApp Image *.jpeg' |
        Sort-Object -Property Name
)

$labels = @()
foreach ($group in @('01', '02', '04', '05', '06', '07', '08', '09')) {
    $labels += "$group-1.jpeg", "$group-2.jpeg"
}
$labels += '10-1.jpeg', '10-2.jpeg', '10-3.jpeg'

if ($files.Count -ne $labels.Count) {
    throw "Se esperaban $($labels.Count) imágenes y se encontraron $($files.Count). No se renombró ningún archivo."
}

$conflicts = @(
    $labels | Where-Object {
        Test-Path -LiteralPath (Join-Path $PSScriptRoot $_)
    }
)
if ($conflicts.Count -gt 0) {
    throw "Ya existen estos nombres de destino: $($conflicts -join ', '). No se renombró ningún archivo."
}

for ($i = 0; $i -lt $files.Count; $i++) {
    Rename-Item -LiteralPath $files[$i].FullName -NewName $labels[$i]
}

Write-Output "Se renombraron $($files.Count) imágenes."
