gunicorn api.route:app --workers 4 --worker-class uvicorn.workers.UvicornWorker --bind 0.0.0.0:9991 2>&1 | tee -a "all_logs_$(date +%F).log"

# uvicorn api.route:app --host 0.0.0.0 --port 9991 --reload
