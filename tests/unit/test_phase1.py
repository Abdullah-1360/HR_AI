"""
tests/unit/test_phase1.py
Unit tests for Phase 1 features using standard unittest:
- Tenant header dependency parsing
- Async task store management
"""
import unittest
from app.deps import get_current_tenant
from app.services.tasks import (
    create_task_record,
    update_task_progress,
    get_task_status,
)

class TestPhase1(unittest.TestCase):
    def test_get_current_tenant_default(self):
        tenant = get_current_tenant()
        self.assertEqual(tenant, "default")

    def test_get_current_tenant_header(self):
        tenant = get_current_tenant(x_tenant_id="tenant_org_42")
        self.assertEqual(tenant, "tenant_org_42")

    def test_task_store_lifecycle(self):
        task_id = create_task_record(task_type="test_ingestion", tenant_id="org_1")
        status = get_task_status(task_id)

        self.assertIsNotNone(status)
        self.assertEqual(status["status"], "pending")
        self.assertEqual(status["progress"], 0)
        self.assertEqual(status["tenant_id"], "org_1")

        update_task_progress(task_id, "processing", 50, "Halfway done")
        status_mid = get_task_status(task_id)
        self.assertEqual(status_mid["status"], "processing")
        self.assertEqual(status_mid["progress"], 50)

        update_task_progress(task_id, "completed", 100, "Done", result={"id": 123})
        status_final = get_task_status(task_id)
        self.assertEqual(status_final["status"], "completed")
        self.assertEqual(status_final["progress"], 100)
        self.assertEqual(status_final["result"], {"id": 123})

if __name__ == "__main__":
    unittest.main()
