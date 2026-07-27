# Data Retention and Deletion

SmartAudit stores uploaded PDFs under the configured managed storage directory and stores task, risk, and callback metadata in MySQL. Vector index data is maintained by the Python service.

Completed and failed tasks are retained for 90 days by default. The scheduled cleanup runs daily and can be configured with `SMARTAUDIT_RETENTION_DAYS` and `SMARTAUDIT_RETENTION_CRON`. Disabling cleanup with `SMARTAUDIT_RETENTION_ENABLED=false` is intended only when an operator supplies an equivalent external retention process.

Deleting a task performs the following actions:

1. logically deletes the task record;
2. deletes related risk items and callback records;
3. requests deletion of the task's Python vector index;
4. deletes the PDF only when its normalized path is inside the managed storage directory;
5. closes any active SSE connection for the task.

Database backups, object-storage replicas, external model-provider records, and infrastructure logs are outside this application cleanup job. Operators must define matching retention periods for those systems and document any legal hold process. A legal hold should disable deletion only for the specifically identified records, not for the whole deployment.
