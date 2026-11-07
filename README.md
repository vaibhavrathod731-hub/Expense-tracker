# SmartSpend

SmartSpend is a local, single-user expense tracker and financial analytics
application built with Python and Streamlit. The project includes application
configuration, an initialized SQLite database, parameterized CRUD repositories,
synthetic demo transactions, transaction management, and automated tests.
The Dashboard displays filtered summaries, category insights, monthly comparisons,
and interactive charts based on persisted transactions.

## Requirements

- Python 3.11 or newer
- PowerShell (commands below are for a VS Code terminal on Windows)

## Set up the environment

Run these commands from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

If PowerShell prevents environment activation, run this in the current terminal
before activating:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

## Run the application and tests

```powershell
streamlit run app.py
python -m pytest
```

The Dashboard analytics use persisted SQLite transactions. Its Month, Year, and
Custom range filters control period income, expenses, savings, savings rate,
and charts; current balance remains all-time income minus all-time expenses.
Synthetic transactions are not automatically inserted into or mixed with user
data. Use the Transactions navigation item to add, filter, edit, and delete
persisted transactions. The Budgets page lets you set monthly expense-category
limits, track utilization, and view warnings at 75%, 90%, and 100% usage.
Dashboard budget totals cover the calendar months overlapping the selected
date range and include spend only for categories with configured budgets. On
startup, the app initializes the local schema and default categories.

## Configuration and local data

By default, the SQLite database is stored at
`data/smartspend.sqlite3` under the current working directory. Set
`SMARTSPEND_DATA_DIR` to use another local directory. SQLite database files are
excluded from Git; do not force-add databases containing personal financial
data.

Initialize the schema and default categories from Python:

```python
from smartspend.db import initialize_database, open_connection
from smartspend.repositories.categories import list_categories

database_path = initialize_database()
with open_connection(database_path) as connection:
    categories = list_categories(connection)
```

Repository monetary amounts use integer paise (`100 paise = ₹1`). Default
categories are seeded idempotently; demo transactions are not imported.

## Project layout

```text
app.py                      Streamlit application entry point
src/smartspend/             Installable Python package
  config.py                 Local application settings and data paths
  demo_data.py              Synthetic records for demos and tests
  db/                       SQLite connections, schema, errors, and records
  repositories/             Parameterized CRUD operations
  services/                 Transaction, analytics, and budget business rules
  ui/                       Streamlit dashboard, transaction, and budget pages
tests/                      Pytest fixtures and automated tests
pyproject.toml              Package metadata, dependencies, and tool settings
```

## Development roadmap

1. Establish the project foundation, configuration, and test setup. (Complete)
2. Add the SQLite schema, initialization, and repository layer. (Complete)
3. Implement transaction management and validation. (Complete)
4. Build dashboard summaries and analytics. (Complete)
5. Add forecasting and downloadable reports. (Budget management complete)
6. Polish the interface, documentation, and test coverage.
