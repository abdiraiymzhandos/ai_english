# Environment and deployment — deprecated pointer

Detailed environment, dependency, deployment, static/media, backup, restore, monitoring, and incident guidance moved to [docs/ENVIRONMENT_AND_OPERATIONS.md](docs/ENVIRONMENT_AND_OPERATIONS.md) on 2026-07-10.

Do not restore live credentials, host identifiers, payment-recipient data, or machine-specific paths to this file.

For the packaged Kazakhstan timezone, local verification, exact PythonAnywhere commands and rollback of the single Always-on Task, follow the [timezone and worker cutover](docs/ENVIRONMENT_AND_OPERATIONS.md#timezone-and-worker-cutover). After a worker code or dependency change, restart the task as well as reloading the web app.
