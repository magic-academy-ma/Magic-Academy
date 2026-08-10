import unittest

from sqlalchemy import CheckConstraint
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base
from app.domain import models  # noqa: F401


class SchemaModelTests(unittest.TestCase):
    def test_erd_v1_tables_are_registered(self) -> None:
        self.assertEqual(
            set(Base.metadata.tables),
            {
                "users",
                "simulations",
                "locations",
                "agents",
                "student_profiles",
                "professor_profiles",
                "agent_states",
                "agent_memories",
                "relationships",
                "runtime_results",
                "organizations",
                "organization_memberships",
                "events",
                "event_participants",
            },
        )

    def test_primary_and_foreign_keys_use_postgresql_uuid(self) -> None:
        for table in Base.metadata.tables.values():
            for primary_key in table.primary_key.columns:
                self.assertIsInstance(primary_key.type, UUID)
            for foreign_key in table.foreign_keys:
                self.assertIsInstance(foreign_key.parent.type, UUID)

    def test_required_unique_constraints_and_indexes_exist(self) -> None:
        expected_names = {
            "uq_locations_simulation_code",
            "uq_users_username",
            "idx_simulations_owner_created",
            "uq_agents_simulation_id_id",
            "uq_agents_simulation_fixture_key",
            "uq_agents_active_user_persona",
            "uq_agent_states_agent_id",
            "uq_relationships_pair",
            "uq_runtime_results_idempotency_key",
            "uq_organizations_simulation_type_name",
            "uq_organizations_simulation_id_id",
            "uq_organization_memberships_active",
            "uq_event_participants_event_agent",
            "idx_agents_simulation_id",
            "idx_agents_runtime_active",
            "idx_agent_memories_agent_occurred",
            "idx_agent_memories_cleanup",
            "idx_relationships_source_updated",
            "idx_events_simulation_started",
            "idx_organizations_simulation_id",
        }
        actual_names = {
            item.name
            for table in Base.metadata.tables.values()
            for item in (*table.constraints, *table.indexes)
            if item.name
        }
        self.assertTrue(expected_names <= actual_names)

    def test_cross_simulation_references_use_composite_foreign_keys(self) -> None:
        expected_targets = {
            "agent_states": {"agents", "locations"},
            "relationships": {"agents"},
            "organization_memberships": {"agents", "organizations"},
            "events": {"locations"},
        }
        for table_name, target_names in expected_targets.items():
            table = Base.metadata.tables[table_name]
            composite_targets = {
                constraint.referred_table.name
                for constraint in table.foreign_key_constraints
                if len(constraint.elements) == 2
            }
            self.assertEqual(composite_targets, target_names)

    def test_memory_cleanup_order_has_created_tick(self) -> None:
        created_tick = Base.metadata.tables["agent_memories"].c.created_tick
        self.assertFalse(created_tick.nullable)
        self.assertEqual(created_tick.type.python_type, int)

    def test_slice_zero_owner_and_fixture_columns_exist(self) -> None:
        simulations = Base.metadata.tables["simulations"]
        agents = Base.metadata.tables["agents"]
        self.assertFalse(simulations.c.owner_id.nullable)
        self.assertTrue({"fixture_key", "fixture_version"} <= set(agents.c.keys()))
        self.assertFalse(agents.c.fixture_key.nullable)
        self.assertFalse(agents.c.fixture_version.nullable)
        self.assertNotIn("grade", agents.c)

    def test_role_profiles_use_agent_id_as_primary_and_foreign_key(self) -> None:
        student_profiles = Base.metadata.tables["student_profiles"]
        professor_profiles = Base.metadata.tables["professor_profiles"]
        for table in (student_profiles, professor_profiles):
            self.assertEqual(list(table.primary_key.columns.keys()), ["agent_id"])
            self.assertEqual(
                {foreign_key.target_fullname for foreign_key in table.c.agent_id.foreign_keys},
                {"agents.id"},
            )
        self.assertTrue({"grade", "interest_field"} <= set(student_profiles.c.keys()))
        self.assertTrue({"academic_rank", "specialty"} <= set(professor_profiles.c.keys()))

    def test_big_five_constraints_use_signed_five_point_steps(self) -> None:
        agents = Base.metadata.tables["agents"]
        constraints = {
            constraint.name: str(constraint.sqltext)
            for constraint in agents.constraints
            if isinstance(constraint, CheckConstraint)
        }
        for column in (
            "openness",
            "conscientiousness",
            "extraversion",
            "agreeableness",
            "emotional_stability",
        ):
            expression = constraints[f"ck_agents_{column}"]
            self.assertIn("BETWEEN -50 AND 50", expression)
            self.assertIn("% 5 = 0", expression)

    def test_embedding_column_is_deferred_until_dimension_is_decided(self) -> None:
        self.assertNotIn("embedding", Base.metadata.tables["agent_memories"].c)


if __name__ == "__main__":
    unittest.main()
