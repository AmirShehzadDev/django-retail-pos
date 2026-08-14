from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class DeploymentContractTests(SimpleTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.root = Path(settings.BASE_DIR)

    def test_runtime_uses_gunicorn_without_waitress(self):
        requirements = (self.root / "requirements/base.txt").read_text(encoding="utf-8")
        dockerfile = (self.root / "Dockerfile").read_text(encoding="utf-8")

        self.assertIn("gunicorn==26.0.0", requirements)
        self.assertNotIn("waitress", requirements.lower())
        self.assertIn('CMD ["gunicorn"', dockerfile)
        self.assertIn("USER pos", dockerfile)
        self.assertIn("npm run css:build", dockerfile)
        self.assertIn("collectstatic --noinput", dockerfile)

    def test_tailwind_image_stage_scans_every_configured_source(self):
        dockerfile = (self.root / "Dockerfile").read_text(encoding="utf-8")
        build_position = dockerfile.index("RUN npm run css:build")

        for source_copy in (
            "COPY templates ./templates",
            "COPY apps ./apps",
            "COPY static/js ./static/js",
        ):
            self.assertIn(source_copy, dockerfile)
            self.assertLess(dockerfile.index(source_copy), build_position)

    def test_compose_preserves_data_and_waits_for_database(self):
        compose = (self.root / "compose.yaml").read_text(encoding="utf-8")
        environment = (self.root / ".env.example").read_text(encoding="utf-8")

        self.assertIn('name: "${COMPOSE_PROJECT_NAME:-pos_codex}"', compose)
        self.assertIn("COMPOSE_PROJECT_NAME=pos_codex", environment)
        self.assertIn(
            'image: "${POS_APP_IMAGE:-pos-codex}:${POS_APP_VERSION:-development}"',
            compose,
        )
        self.assertIn('"${POS_APP_BIND:-127.0.0.1}:${POS_APP_PORT:-8000}:8000"', compose)
        self.assertIn("condition: service_healthy", compose)
        self.assertGreaterEqual(compose.count("restart: unless-stopped"), 2)
        self.assertIn("postgres_data:/var/lib/postgresql/data", compose)
        self.assertNotIn("python manage.py migrate", compose)

    def test_operational_scripts_never_delete_compose_volumes(self):
        script_text = "\n".join(
            path.read_text(encoding="utf-8") for path in (self.root / "deploy").glob("*.ps1")
        ).lower()

        self.assertNotIn("down -v", script_text)
        self.assertNotIn("down --volumes", script_text)
        self.assertIn("-confirmdatareplacement", script_text)
        self.assertIn("-confirmrollback", script_text)

    def test_release_and_backup_contracts_are_present(self):
        build = (self.root / "deploy/Build-Release.ps1").read_text(encoding="utf-8")
        install = (self.root / "deploy/Install-POS.ps1").read_text(encoding="utf-8")
        update = (self.root / "deploy/Install-Update.ps1").read_text(encoding="utf-8")
        backup = (self.root / "deploy/Backup-Database.ps1").read_text(encoding="utf-8")
        runbook = (self.root / "deploy/README.md").read_text(encoding="utf-8")
        normalized_runbook = " ".join(runbook.split())

        self.assertIn("Get-FileHash -Algorithm SHA256", build)
        self.assertIn("schema_version = 1", build)
        self.assertIn('Join-Path $root "docker/postgres"', build)
        self.assertIn("python manage.py bootstrap_pos", install)
        self.assertNotIn("createsuperuser", install)
        self.assertIn('Purpose "pre-update-', update)
        self.assertIn("pg_dump", backup)
        self.assertIn("pg_restore --list", backup)
        self.assertIn('Filter "pos-*.dump"', backup)
        self.assertIn("Immutable extracted release", runbook)
        self.assertIn("Permanent configuration, scripts, logs, and backups", runbook)
        self.assertIn("Docker named volume", runbook)
        self.assertIn(
            "never copy `.env.example` over an existing shop `.env`",
            normalized_runbook,
        )
