param(
  [string]$Host = '127.0.0.1',
  [int]$Port = 8000
)

$env:PYTHONUTF8 = '1'
python app.py
