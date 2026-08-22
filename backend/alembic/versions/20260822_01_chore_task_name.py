"""Rename the chore task name column.

Revision ID: 20260822_01_chore_task_name
Revises: 20260821_03_household
Create Date: 2026-08-22

"""

from alembic import op

revision: str = "20260822_01_chore_task_name"
down_revision: str | None = "20260821_03_household"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.alter_column("chore_tasks", "name", new_column_name="task_name")
    op.execute(
        "ALTER TABLE chore_tasks RENAME CONSTRAINT ck_chore_tasks_name_trimmed TO ck_chore_tasks_task_name_trimmed"
    )
    op.execute(
        "ALTER TABLE chore_tasks RENAME CONSTRAINT ck_chore_tasks_name_length TO ck_chore_tasks_task_name_length"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE chore_tasks RENAME CONSTRAINT ck_chore_tasks_task_name_length TO ck_chore_tasks_name_length"
    )
    op.execute(
        "ALTER TABLE chore_tasks RENAME CONSTRAINT ck_chore_tasks_task_name_trimmed TO ck_chore_tasks_name_trimmed"
    )
    op.alter_column("chore_tasks", "task_name", new_column_name="name")
