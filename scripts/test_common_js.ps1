$ErrorActionPreference = "Stop"

$root = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$work = Join-Path $env:TEMP "dtcall-common-js-test"

if (Test-Path -LiteralPath $work) {
    Remove-Item -LiteralPath $work -Recurse -Force
}

New-Item -ItemType Directory -Force -Path (Join-Path $work "scripts") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $work "static\js") | Out-Null

Copy-Item -LiteralPath (Join-Path $root "scripts\test_common_js.js") -Destination (Join-Path $work "scripts\test_common_js.js")
Copy-Item -LiteralPath (Join-Path $root "static\js\common.js") -Destination (Join-Path $work "static\js\common.js")

Push-Location $work
try {
    node .\scripts\test_common_js.js
}
finally {
    Pop-Location
}
