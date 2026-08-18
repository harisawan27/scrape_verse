$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($env:DATABASE_URL)) {
    throw 'DATABASE_URL must be set before running migrations.'
}

python "$PSScriptRoot/migrate.py"

