#!/bin/bash
cd backend
source .venv/bin/activate
pip install -q sentence-transformers modal
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &

cd ../frontend
npm install
nohup npm run dev > frontend.log 2>&1 &
echo "Servers starting..."
