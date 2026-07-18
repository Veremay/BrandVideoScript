# Production log files

Install the persistent Docker log exporter once on the ECS host, from the
repository checkout:

```bash
sudo bash deploy/install-log-service.sh
```

The service follows the `backend` and `nginx` containers and appends their
console output to:

```text
/var/log/brandvideo/backend.log
```

The complete log is rotated daily or after it reaches 50 MiB. Fourteen
rotations are kept and old rotations are compressed. Check the service and
follow the log:

```bash
sudo systemctl status brandvideo-log
sudo tail -F /var/log/brandvideo/backend.log
```

Project-tagged records are additionally written to
`/var/log/brandvideo/projects/<project_id>/backend.log`, with the same rotation
policy. Read or follow one project with:

```bash
sudo bash deploy/project-logs.sh PROJECT_ID
sudo bash deploy/project-logs.sh --follow PROJECT_ID
```

Container startup messages, health checks, and failures that happen before a
project is identified do not have a `project_id`; they remain available only
in the main log. Concurrent raw token streams can interleave at Docker stdout;
their request and project marker is emitted at the start of each stream.
