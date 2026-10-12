$ErrorActionPreference = "Stop"

$projectDirectory = $PSScriptRoot
$parentDirectory = Split-Path -Parent $projectDirectory
$outputFile = Join-Path $parentDirectory "web-prototype-share.zip"
$temporaryRoot = Join-Path $env:TEMP ("web-prototype-share-" + [guid]::NewGuid().ToString("N"))
$stagingDirectory = Join-Path $temporaryRoot "web-prototype"

New-Item -ItemType Directory -Path $stagingDirectory -Force | Out-Null

$excludedNames = @(
    "node_modules",
    ".git",
    ".DS_Store"
)

Get-ChildItem -LiteralPath $projectDirectory -Force |
    Where-Object { $excludedNames -notcontains $_.Name } |
    ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $stagingDirectory -Recurse -Force
    }

if (Test-Path -LiteralPath $outputFile) {
    Remove-Item -LiteralPath $outputFile -Force
}

Compress-Archive -LiteralPath $stagingDirectory -DestinationPath $outputFile -CompressionLevel Optimal
Remove-Item -LiteralPath $temporaryRoot -Recurse -Force

Write-Host "Paylasim paketi olusturuldu:"
Write-Host $outputFile
