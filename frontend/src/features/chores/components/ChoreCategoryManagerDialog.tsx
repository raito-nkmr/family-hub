import { useTranslation } from 'react-i18next'
import { CategoryManagerDialog, type CategoryManagerCopy } from '../../../shared/ui/CategoryManagerDialog'
import type { ChoreCategory } from '../api'

interface ChoreCategoryManagerDialogProps {
  categories: ChoreCategory[]
  submitting: boolean
  actionId: string | null
  error: string | null
  onCreate: (categoryName: string) => Promise<boolean>
  onRename: (categoryId: string, categoryName: string) => Promise<boolean>
  onDelete: (category: ChoreCategory) => Promise<boolean>
  onReorder: (categoryIds: string[]) => Promise<boolean>
  onClose: () => void
}

export function ChoreCategoryManagerDialog({
  categories,
  submitting,
  actionId,
  error,
  onCreate,
  onRename,
  onDelete,
  onReorder,
  onClose,
}: ChoreCategoryManagerDialogProps) {
  const { t } = useTranslation()
  const copy: CategoryManagerCopy = {
    title: t('chores.categoryManage'),
    help: t('chores.categoryManageHelp'),
    name: t('chores.categoryName'),
    placeholder: t('chores.categoryNamePlaceholder'),
    add: t('chores.categoryCreate'),
    noCategories: t('chores.noCategories'),
    moveUp: (categoryName) => t('chores.moveCategoryUp', { categoryName }),
    moveDown: (categoryName) => t('chores.moveCategoryDown', { categoryName }),
    edit: (categoryName) => t('chores.editCategory', { categoryName }),
    delete: (categoryName) => t('chores.deleteCategory', { categoryName }),
  }

  return (
    <CategoryManagerDialog
      categories={categories}
      copy={copy}
      idPrefix="chore-category"
      submitting={submitting}
      actionId={actionId}
      error={error}
      onCreate={onCreate}
      onRename={onRename}
      onDelete={onDelete}
      onReorder={onReorder}
      onClose={onClose}
    />
  )
}
