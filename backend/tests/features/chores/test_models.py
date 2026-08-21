from app.features.chores.models import ChoreCategory, ChoreCompletion, ChoreTask


def test_chore_category_constraints_and_indexes_are_named() -> None:
    constraint_names = {constraint.name for constraint in ChoreCategory.__table__.constraints}
    index_names = {index.name for index in ChoreCategory.__table__.indexes}

    assert "pk_chore_categories" in constraint_names
    assert "ck_chore_categories_name_trimmed" in constraint_names
    assert "ck_chore_categories_name_length" in constraint_names
    assert "ck_chore_categories_sort_order" in constraint_names
    assert "ix_chore_categories_group_id" in index_names
    assert "ix_chore_categories_group_sort_order" in index_names
    assert "uq_chore_categories_group_name_ci" in index_names
    assert ChoreCategory.__table__.c.name.nullable is False


def test_chore_task_constraints_and_indexes_are_named() -> None:
    constraint_names = {constraint.name for constraint in ChoreTask.__table__.constraints}
    index_names = {index.name for index in ChoreTask.__table__.indexes}

    assert "pk_chore_tasks" in constraint_names
    assert "ck_chore_tasks_name_trimmed" in constraint_names
    assert "ck_chore_tasks_name_length" in constraint_names
    assert "ck_chore_tasks_interval_days" in constraint_names
    assert "ix_chore_tasks_group_id_is_active" in index_names
    assert "ix_chore_tasks_category_id" in index_names
    assert ChoreTask.__table__.c.category_id.nullable is False


def test_chore_completion_indexes_are_named() -> None:
    constraint_names = {constraint.name for constraint in ChoreCompletion.__table__.constraints}
    index_names = {index.name for index in ChoreCompletion.__table__.indexes}

    assert "pk_chore_completions" in constraint_names
    assert "ck_chore_completions_task_name_trimmed" in constraint_names
    assert "ck_chore_completions_task_name_length" in constraint_names
    assert "ck_chore_completions_category_name_trimmed" in constraint_names
    assert "ck_chore_completions_category_name_length" in constraint_names
    assert "ix_chore_completions_task_id_completed_at" in index_names
    assert "ix_chore_completions_completed_at_task_id" in index_names
    assert ChoreCompletion.__table__.c.task_name_snapshot.nullable is False
    assert ChoreCompletion.__table__.c.category_name_snapshot.nullable is False
    assert ChoreCompletion.__table__.c.category_id.nullable is True
