# Open-Source To-Do / Task Management Application

A Flask and SQLite task manager for the OST CA3/CA4 mini-project. Users can create, view, edit, complete, delete, search, and filter tasks. A dataset explorer supports browsing and importing task examples from Microsoft's real-world MS-LaTTE dataset.

## Dataset
**MS-LaTTE: A Dataset of Where and When To-do Tasks are Completed**  
Official repository: https://github.com/microsoft/MS-LaTTE  
Dataset file: https://github.com/microsoft/MS-LaTTE/blob/main/MS-LaTTE.json  
Dataset license: CDLA-Permissive-2.0. See the official repository and include its license text when redistributing the data.

MS-LaTTE contains 10,101 real-world to-do tasks with human annotations about likely completion locations and times of day. These are contextual annotations, not individual due dates, priority levels, or live task statuses. This application uses the dataset for task discovery and example import; users' own task details are stored separately in SQLite.

Download the dataset:
```bash
python fetch_dataset.py
```

## Run locally
Python 3.10+:
```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python fetch_dataset.py
python app.py
```
Open http://localhost:5000.

## Run with Docker Compose
```bash
docker compose up --build
```
Open http://localhost:5000. The SQLite database is stored in a named volume and persists across container recreation. Stop with Ctrl+C or run `docker compose down`.

## Features
- Create, edit, delete and complete tasks
- Assign priority and due date
- Track Pending, In Progress and Completed statuses
- Search and filter tasks
- Browse MS-LaTTE records and import a task example
- Health endpoint at `/health`

## Architecture
Browser → Flask application container → SQLite database in a persistent Docker volume. The MS-LaTTE JSON file is mounted read-only into the application container.

## License
Application source code: MIT. Dataset: separately licensed under CDLA-Permissive-2.0.
