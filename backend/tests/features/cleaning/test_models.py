from app.features.cleaning.models import CleaningCategory, CleaningCompletion, CleaningTask


def test_cleaning_category_constraints_and_indexes_are_named() -> None:
    constraint_names = {constraint.name for constraint in CleaningCategory.__table__.constraints}
    index_names = {index.name for index in CleaningCategory.__table__.indexes}

    assert "pk_cleaning_categories" in constraint_names
    assert "ck_cleaning_categories_name_trimmed" in constraint_names
    assert "ck_cleaning_categories_name_length" in constraint_names
    assert "ix_cleaning_categories_group_id" in index_names
    assert "uq_cleaning_categories_group_name_ci" in index_names
    assert CleaningCategory.__table__.c.name.nullable is False


def test_cleaning_task_constraints_and_indexes_are_named() -> None:
    constraint_names = {constraint.name for constraint in CleaningTask.__table__.constraints}
    index_names = {index.name for index in CleaningTask.__table__.indexes}

    assert "pk_cleaning_tasks" in constraint_names
    assert "ck_cleaning_tasks_name_trimmed" in constraint_names
    assert "ck_cleaning_tasks_name_length" in constraint_names
    assert "ck_cleaning_tasks_interval_days" in constraint_names
    assert "ix_cleaning_tasks_group_id_is_active" in index_names
    assert "ix_cleaning_tasks_category_id" in index_names
    assert CleaningTask.__table__.c.category_id.nullable is False


def test_cleaning_completion_indexes_are_named() -> None:
    constraint_names = {constraint.name for constraint in CleaningCompletion.__table__.constraints}
    index_names = {index.name for index in CleaningCompletion.__table__.indexes}

    assert "pk_cleaning_completions" in constraint_names
    assert "ck_cleaning_completions_task_name_trimmed" in constraint_names
    assert "ck_cleaning_completions_task_name_length" in constraint_names
    assert "ck_cleaning_completions_category_name_trimmed" in constraint_names
    assert "ck_cleaning_completions_category_name_length" in constraint_names
    assert "ix_cleaning_completions_task_id_completed_at" in index_names
    assert "ix_cleaning_completions_completed_at_task_id" in index_names
    assert CleaningCompletion.__table__.c.task_name_snapshot.nullable is False
    assert CleaningCompletion.__table__.c.category_name_snapshot.nullable is False
    assert CleaningCompletion.__table__.c.category_id.nullable is True
