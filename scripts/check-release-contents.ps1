param([Parameter(Mandatory = $true)][string]$Path)

$ErrorActionPreference = "Stop"
$root = (Resolve-Path -LiteralPath $Path).Path
$forbidden = '(^|[\\/])(\.env($|[\\/])|env\.deploy$|logs($|[\\/])|storage($|[\\/])|models($|[\\/])|node_modules($|[\\/])|target($|[\\/])|dist($|[\\/])|coverage($|[\\/])|test-results($|[\\/])|\.git($|[\\/]))|\.(pem|key|p12|pfx|jks|db|sqlite|log)$'

$violations = Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object {
  $relative = $_.FullName.Substring($root.Length).TrimStart('\', '/')
  $relative -match $forbidden -or $_.Length -gt 100MB
}

if ($violations) {
  $violations.FullName | ForEach-Object { Write-Error "Forbidden release content: $_" }
  exit 1
}

Write-Host "Release content check passed."
