from app.features.cleaning.models import CleaningCompletion, CleaningTask


def test_cleaning_task_constraints_and_indexes_are_named() -> None:
    constraint_names = {constraint.name for constraint in CleaningTask.__table__.constraints}
    index_names = {index.name for index in CleaningTask.__table__.indexes}

    assert "pk_cleaning_tasks" in constraint_names
    assert "ck_cleaning_tasks_name_trimmed" in constraint_names
    assert "ck_cleaning_tasks_name_length" in constraint_names
    assert "ck_cleaning_tasks_interval_days" in constraint_names
    assert "ix_cleaning_tasks_group_id_is_active" in index_names


def test_cleaning_completion_indexes_are_named() -> None:
    constraint_names = {constraint.name for constraint in CleaningCompletion.__table__.constraints}
    index_names = {index.name for index in CleaningCompletion.__table__.indexes}

    assert "pk_cleaning_completions" in constraint_names
    assert "ix_cleaning_completions_task_id_completed_at" in index_names
