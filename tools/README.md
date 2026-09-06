# FlowSlide Tools Inventory

This directory contains administrative and diagnostic tooling for FlowSlide database management and deployment verification.

## Tool Index

| Tool | Module / Scope | Description |
| :--- | :--- | :--- |
| 	ools/list_users.py | Database / Auth | Inspects database tables, user columns, and user records with password hash prefixes and timestamps from DATABASE_URL. |
| 	ools/clear_external_db.py | Database | Cleans up test user records and external database entities safely. |
| 	ools/run_auto_detection_checks.py | Core / Deployment | Validates storage policies, deployment modes, and database connection detection. |

## Usage

Ensure DATABASE_URL is set in your environment before running database tools:

`ash
python tools/list_users.py
`
