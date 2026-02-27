$ErrorActionPreference = 'Stop'

Write-Host '[1/4] Python syntax check'
python -m py_compile app.py config.py utils\cache.py utils\model_fetcher.py utils\novel_workflow.py utils\openrouter_api.py

Write-Host '[2/4] Basic route check (imports only)'
python -c "from app import app; print('routes:', len(app.routes))"

Write-Host '[3/4] Env template exists'
if (-not (Test-Path .env.example)) { throw '.env.example missing' }

Write-Host '[4/4] Done'
