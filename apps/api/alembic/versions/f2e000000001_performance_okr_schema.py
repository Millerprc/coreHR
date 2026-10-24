# Copyright (c) 2026 coreHR 项目贡献者
# 许可证：coreHR Sustainable Use License v1.0（见仓库根目录 LICENSE）。本文件不是 OSI 开源。

"""add performance OKR cycle objective and key result tables

Revision ID: f2e000000001
Revises: f2d000000001
Create Date: 2026-10-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "f2e000000001"
down_revision: str | Sequence[str] | None = "f2d000000001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            CREATE TABLE performance_cycles (
                id UUID NOT NULL,
                code VARCHAR(50) NOT NULL,
                name VARCHAR(200) NOT NULL,
                cycle_type VARCHAR(30) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                status VARCHAR(30) NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                CONSTRAINT pk_performance_cycles PRIMARY KEY (id),
                CONSTRAINT uq_performance_cycles_code UNIQUE (code),
                CONSTRAINT ck_performance_cycles_cycle_date_order
                    CHECK (end_date >= start_date),
                CONSTRAINT ck_performance_cycles_cycle_type_allowed
                    CHECK (cycle_type IN ('quarterly', 'annual', 'special')),
                CONSTRAINT ck_performance_cycles_cycle_status_allowed
                    CHECK (status IN ('draft', 'active', 'closed'))
            )
            """
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX ix_performance_cycles_status "
            "ON performance_cycles (status)"
        )
    )
    connection.execute(
        sa.text(
            """
            CREATE TABLE performance_objectives (
                id UUID NOT NULL,
                cycle_id UUID NOT NULL,
                person_id UUID NOT NULL,
                title VARCHAR(300) NOT NULL,
                description TEXT,
                weight NUMERIC(7, 2) NOT NULL,
                status VARCHAR(30) NOT NULL,
                sequence_no INTEGER NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                CONSTRAINT pk_performance_objectives PRIMARY KEY (id),
                CONSTRAINT ck_performance_objectives_objective_weight_positive
                    CHECK (weight > 0),
                CONSTRAINT ck_performance_objectives_objective_weight_upper_bound
                    CHECK (weight <= 100),
                CONSTRAINT ck_performance_objectives_objective_status_allowed
                    CHECK (status IN ('draft', 'submitted', 'approved', 'archived')),
                CONSTRAINT fk_performance_objectives_cycle_id_performance_cycles
                    FOREIGN KEY (cycle_id) REFERENCES performance_cycles (id),
                CONSTRAINT fk_performance_objectives_person_id_persons
                    FOREIGN KEY (person_id) REFERENCES persons (id)
            )
            """
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX ix_performance_objectives_cycle_id "
            "ON performance_objectives (cycle_id)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX ix_performance_objectives_person_id "
            "ON performance_objectives (person_id)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX ix_performance_objectives_status "
            "ON performance_objectives (status)"
        )
    )
    connection.execute(
        sa.text(
            """
            CREATE TABLE performance_key_results (
                id UUID NOT NULL,
                objective_id UUID NOT NULL,
                title VARCHAR(300) NOT NULL,
                description TEXT,
                target_value NUMERIC(20, 4),
                actual_value NUMERIC(20, 4),
                unit VARCHAR(50),
                weight NUMERIC(7, 2) NOT NULL,
                score NUMERIC(5, 2),
                status VARCHAR(30) NOT NULL,
                sequence_no INTEGER NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
                CONSTRAINT pk_performance_key_results PRIMARY KEY (id),
                CONSTRAINT ck_performance_key_results_key_result_weight_positive
                    CHECK (weight > 0),
                CONSTRAINT ck_performance_key_results_key_result_weight_upper_bound
                    CHECK (weight <= 100),
                CONSTRAINT ck_performance_key_results_key_result_score_range
                    CHECK (score IS NULL OR (score >= 0 AND score <= 100)),
                CONSTRAINT ck_performance_key_results_key_result_status_allowed
                    CHECK (status IN ('draft', 'submitted', 'approved', 'archived')),
                CONSTRAINT fk_performance_key_results_objective_id_performance_objectives
                    FOREIGN KEY (objective_id) REFERENCES performance_objectives (id)
            )
            """
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX ix_performance_key_results_objective_id "
            "ON performance_key_results (objective_id)"
        )
    )
    connection.execute(
        sa.text(
            "CREATE INDEX ix_performance_key_results_status "
            "ON performance_key_results (status)"
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    # Requirement: HR-PERF-014 — 按外键反序删除，先删子表再删父表，回滚不留残留。
    connection.execute(sa.text("DROP TABLE performance_key_results"))
    connection.execute(sa.text("DROP TABLE performance_objectives"))
    connection.execute(sa.text("DROP TABLE performance_cycles"))
