"""create ERD-based schema v1

Revision ID: 20260805_0001
Revises:
Create Date: 2026-08-05
"""

from alembic import op

revision = "20260805_0001"
down_revision = None
branch_labels = None
depends_on = None


def _execute_batch(sql: str) -> None:
    for statement in sql.split(";"):
        if statement.strip():
            op.execute(statement)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    _execute_batch(
        """
        CREATE TABLE simulations (
            id UUID PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            status VARCHAR(20) NOT NULL DEFAULT 'ready' CONSTRAINT ck_simulations_status CHECK (status IN ('ready','running','paused','completed','failed')),
            current_day INTEGER NOT NULL DEFAULT 1 CONSTRAINT ck_simulations_current_day CHECK (current_day >= 1),
            current_tick BIGINT NOT NULL DEFAULT 0 CONSTRAINT ck_simulations_current_tick CHECK (current_tick >= 0),
            magic_enabled BOOLEAN NOT NULL DEFAULT true,
            started_at TIMESTAMPTZ,
            ended_at TIMESTAMPTZ,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE locations (
            id UUID PRIMARY KEY,
            simulation_id UUID NOT NULL CONSTRAINT fk_locations_simulation REFERENCES simulations(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            code VARCHAR(50) NOT NULL,
            name VARCHAR(100) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_locations_simulation_code UNIQUE (simulation_id, code),
            CONSTRAINT uq_locations_simulation_id_id UNIQUE (simulation_id, id)
        );

        CREATE TABLE agents (
            id UUID PRIMARY KEY,
            simulation_id UUID NOT NULL CONSTRAINT fk_agents_simulation REFERENCES simulations(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            agent_type VARCHAR(20) NOT NULL CONSTRAINT ck_agents_agent_type CHECK (agent_type IN ('student','professor','user_persona')),
            name VARCHAR(50) NOT NULL,
            gender VARCHAR(20) CONSTRAINT ck_agents_gender CHECK (gender IS NULL OR gender IN ('male','female','non_binary','unspecified')),
            personality_type VARCHAR(30),
            mbti_type VARCHAR(4) NOT NULL CONSTRAINT ck_agents_mbti_type CHECK (mbti_type IN ('ISTJ','ESTP','INFP','ENTJ','ESFJ')),
            openness SMALLINT NOT NULL DEFAULT 50 CONSTRAINT ck_agents_openness CHECK (openness BETWEEN 0 AND 100),
            conscientiousness SMALLINT NOT NULL DEFAULT 50 CONSTRAINT ck_agents_conscientiousness CHECK (conscientiousness BETWEEN 0 AND 100),
            extraversion SMALLINT NOT NULL DEFAULT 50 CONSTRAINT ck_agents_extraversion CHECK (extraversion BETWEEN 0 AND 100),
            agreeableness SMALLINT NOT NULL DEFAULT 50 CONSTRAINT ck_agents_agreeableness CHECK (agreeableness BETWEEN 0 AND 100),
            emotional_stability SMALLINT NOT NULL DEFAULT 50 CONSTRAINT ck_agents_emotional_stability CHECK (emotional_stability BETWEEN 0 AND 100),
            role_description TEXT,
            active_status VARCHAR(30) NOT NULL DEFAULT 'active',
            inactive_until_tick BIGINT CONSTRAINT ck_agents_inactive_until_tick CHECK (inactive_until_tick IS NULL OR inactive_until_tick >= 0),
            persona_locked_at TIMESTAMPTZ,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_agents_simulation_id_id UNIQUE (simulation_id, id)
        );
        CREATE UNIQUE INDEX uq_agents_active_user_persona ON agents (simulation_id) WHERE agent_type = 'user_persona' AND deleted_at IS NULL;
        CREATE INDEX idx_agents_simulation_id ON agents (simulation_id, id ASC);
        CREATE INDEX idx_agents_runtime_active ON agents (simulation_id, active_status, inactive_until_tick);

        CREATE TABLE agent_states (
            id UUID PRIMARY KEY,
            simulation_id UUID NOT NULL CONSTRAINT fk_agent_states_simulation REFERENCES simulations(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            agent_id UUID NOT NULL,
            location_id UUID,
            hunger SMALLINT NOT NULL DEFAULT 50,
            fatigue SMALLINT NOT NULL DEFAULT 0,
            stress SMALLINT NOT NULL DEFAULT 0,
            satisfaction SMALLINT NOT NULL DEFAULT 50,
            mood SMALLINT NOT NULL DEFAULT 0,
            current_action VARCHAR(50),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_agent_states_agent_id UNIQUE (agent_id),
            CONSTRAINT fk_agent_states_agent FOREIGN KEY (simulation_id, agent_id) REFERENCES agents(simulation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            CONSTRAINT fk_agent_states_location FOREIGN KEY (simulation_id, location_id) REFERENCES locations(simulation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            CONSTRAINT ck_agent_states_bounded_scores CHECK (hunger BETWEEN 0 AND 100 AND fatigue BETWEEN 0 AND 100 AND stress BETWEEN 0 AND 100 AND satisfaction BETWEEN 0 AND 100 AND mood BETWEEN -100 AND 100)
        );

        CREATE TABLE organizations (
            id UUID PRIMARY KEY,
            simulation_id UUID NOT NULL CONSTRAINT fk_organizations_simulation REFERENCES simulations(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            organization_type VARCHAR(20) NOT NULL CONSTRAINT ck_organizations_type CHECK (organization_type IN ('major','club','dormitory')),
            name VARCHAR(100) NOT NULL,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT true,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_organizations_simulation_type_name UNIQUE (simulation_id, organization_type, name),
            CONSTRAINT uq_organizations_simulation_id_id UNIQUE (simulation_id, id)
        );
        CREATE INDEX idx_organizations_simulation_id ON organizations (simulation_id, id ASC);

        CREATE TABLE organization_memberships (
            id UUID PRIMARY KEY,
            simulation_id UUID NOT NULL CONSTRAINT fk_memberships_simulation REFERENCES simulations(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            organization_id UUID NOT NULL,
            agent_id UUID NOT NULL,
            membership_role VARCHAR(30) CONSTRAINT ck_memberships_role CHECK (membership_role IS NULL OR membership_role IN ('member','leader','professor','resident')),
            joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            left_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_memberships_organization FOREIGN KEY (simulation_id, organization_id) REFERENCES organizations(simulation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            CONSTRAINT fk_memberships_agent FOREIGN KEY (simulation_id, agent_id) REFERENCES agents(simulation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT
        );
        CREATE UNIQUE INDEX uq_organization_memberships_active ON organization_memberships (organization_id, agent_id) WHERE left_at IS NULL;

        CREATE TABLE events (
            id UUID PRIMARY KEY,
            simulation_id UUID NOT NULL CONSTRAINT fk_events_simulation REFERENCES simulations(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            location_id UUID,
            event_type VARCHAR(30) NOT NULL CONSTRAINT ck_events_type CHECK (event_type IN ('class','group_project','exam','meeting','mt','festival','student_council','random_incident')),
            title VARCHAR(100) NOT NULL,
            description TEXT,
            status VARCHAR(20) NOT NULL DEFAULT 'scheduled' CONSTRAINT ck_events_status CHECK (status IN ('scheduled','ongoing','completed','cancelled')),
            simulation_day INTEGER NOT NULL CONSTRAINT ck_events_simulation_day CHECK (simulation_day >= 1),
            started_at TIMESTAMPTZ,
            ended_at TIMESTAMPTZ,
            metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_events_location FOREIGN KEY (simulation_id, location_id) REFERENCES locations(simulation_id, id) ON DELETE SET NULL (location_id) ON UPDATE RESTRICT
        );
        CREATE INDEX idx_events_simulation_started ON events (simulation_id, started_at DESC, id DESC);

        CREATE TABLE event_participants (
            id UUID PRIMARY KEY,
            event_id UUID NOT NULL CONSTRAINT fk_event_participants_event REFERENCES events(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            agent_id UUID NOT NULL CONSTRAINT fk_event_participants_agent REFERENCES agents(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            participant_role VARCHAR(30),
            action_taken TEXT,
            result JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT uq_event_participants_event_agent UNIQUE (event_id, agent_id)
        );

        CREATE TABLE relationships (
            id UUID PRIMARY KEY,
            simulation_id UUID NOT NULL CONSTRAINT fk_relationships_simulation REFERENCES simulations(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            source_agent_id UUID NOT NULL,
            target_agent_id UUID NOT NULL,
            affection SMALLINT NOT NULL DEFAULT 0 CONSTRAINT ck_relationships_affection CHECK (affection BETWEEN -100 AND 100),
            closeness SMALLINT NOT NULL DEFAULT 0 CONSTRAINT ck_relationships_closeness CHECK (closeness BETWEEN 0 AND 100),
            trust SMALLINT NOT NULL DEFAULT 0 CONSTRAINT ck_relationships_trust CHECK (trust BETWEEN -100 AND 100),
            tension SMALLINT NOT NULL DEFAULT 0 CONSTRAINT ck_relationships_tension CHECK (tension BETWEEN 0 AND 100),
            rivalry SMALLINT NOT NULL DEFAULT 0 CONSTRAINT ck_relationships_rivalry CHECK (rivalry BETWEEN 0 AND 100),
            dependency SMALLINT NOT NULL DEFAULT 0 CONSTRAINT ck_relationships_dependency CHECK (dependency BETWEEN 0 AND 100),
            relationship_type VARCHAR(30) CONSTRAINT ck_relationships_type CHECK (relationship_type IS NULL OR relationship_type IN ('friend','rival','senior_junior','confession','betrayal','reconciliation')),
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            CONSTRAINT fk_relationships_source_agent FOREIGN KEY (simulation_id, source_agent_id) REFERENCES agents(simulation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            CONSTRAINT fk_relationships_target_agent FOREIGN KEY (simulation_id, target_agent_id) REFERENCES agents(simulation_id, id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            CONSTRAINT ck_relationships_distinct_agents CHECK (source_agent_id <> target_agent_id),
            CONSTRAINT uq_relationships_pair UNIQUE (simulation_id, source_agent_id, target_agent_id)
        );
        CREATE INDEX idx_relationships_source_updated ON relationships (source_agent_id, updated_at DESC, id DESC);

        CREATE TABLE agent_memories (
            id UUID PRIMARY KEY,
            agent_id UUID NOT NULL CONSTRAINT fk_agent_memories_agent REFERENCES agents(id) ON DELETE RESTRICT ON UPDATE RESTRICT,
            event_id UUID CONSTRAINT fk_agent_memories_event REFERENCES events(id) ON DELETE SET NULL ON UPDATE RESTRICT,
            content TEXT NOT NULL,
            memory_type VARCHAR(20) NOT NULL DEFAULT 'observation' CONSTRAINT ck_agent_memories_type CHECK (memory_type IN ('observation','conversation','reflection','plan')),
            importance SMALLINT NOT NULL DEFAULT 0 CONSTRAINT ck_agent_memories_importance CHECK (importance BETWEEN 0 AND 100),
            created_tick BIGINT NOT NULL CONSTRAINT ck_agent_memories_created_tick CHECK (created_tick >= 0),
            occurred_at TIMESTAMPTZ NOT NULL,
            last_accessed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX idx_agent_memories_agent_occurred ON agent_memories (agent_id, occurred_at DESC, id DESC);
        CREATE INDEX idx_agent_memories_cleanup ON agent_memories (agent_id, importance ASC, created_tick ASC);
        """
    )


def downgrade() -> None:
    _execute_batch(
        """
        DROP TABLE agent_memories;
        DROP TABLE relationships;
        DROP TABLE event_participants;
        DROP TABLE events;
        DROP TABLE organization_memberships;
        DROP TABLE organizations;
        DROP TABLE agent_states;
        DROP TABLE agents;
        DROP TABLE locations;
        DROP TABLE simulations;
        DROP EXTENSION IF EXISTS vector;
        """
    )
