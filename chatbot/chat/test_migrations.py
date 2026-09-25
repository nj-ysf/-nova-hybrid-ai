from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class LegacyMigrationTests(TransactionTestCase):
    def test_existing_messages_preserved_without_inventing_ownership(self):
        executor = MigrationExecutor(connection)
        targets = executor.loader.graph.leaf_nodes()
        try:
            executor.migrate([("chat", "0001_initial")])
            state = executor.loader.project_state([("chat", "0001_initial")]).apps
            conversation = state.get_model("chat", "Conversation").objects.create(title="Legacy")
            state.get_model("chat", "ChatMessage").objects.create(
                conversation=conversation, role="user", content="Preserve me"
            )
            executor = MigrationExecutor(connection)
            executor.migrate(targets)
            from chat.models import Conversation

            migrated = Conversation.objects.get(pk=conversation.pk)
            self.assertIsNone(migrated.user_id)
            self.assertIsNone(migrated.project_id)
            self.assertEqual(migrated.messages.get().content, "Preserve me")
            self.assertEqual(migrated.messages.get().classification, 3)
        finally:
            MigrationExecutor(connection).migrate(targets)
