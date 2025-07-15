# run.ps1
$env:PYTHONPATH = "."
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
