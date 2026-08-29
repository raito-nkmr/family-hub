import { useTranslation } from 'react-i18next'
import { CategoryManagerDialog, type CategoryManagerCopy } from '../../../shared/ui/CategoryManagerDialog'
import type { ShoppingCategory } from '../api'

interface ShoppingCategoryManagerDialogProps {
  categories: ShoppingCategory[]
  submitting: boolean
  actionId: string | null
  error: string | null
  onCreate: (categoryName: string) => Promise<boolean>
  onRename: (categoryId: string, categoryName: string) => Promise<boolean>
  onDelete: (category: ShoppingCategory) => Promise<boolean>
  onReorder: (categoryIds: string[]) => Promise<boolean>
  onClose: () => void
}

export function ShoppingCategoryManagerDialog({
  categories,
  submitting,
  actionId,
  error,
  onCreate,
  onRename,
  onDelete,
  onReorder,
  onClose,
}: ShoppingCategoryManagerDialogProps) {
  const { t } = useTranslation()
  const copy: CategoryManagerCopy = {
    title: t('shopping.categoryManage'),
    help: t('shopping.categoryManageHelp'),
    name: t('shopping.categoryName'),
    placeholder: t('shopping.categoryPlaceholder'),
    add: t('shopping.categoryAdd'),
    noCategories: t('shopping.noCategories'),
    moveUp: (categoryName) => t('shopping.moveCategoryUp', { categoryName }),
    moveDown: (categoryName) => t('shopping.moveCategoryDown', { categoryName }),
    edit: (categoryName) => t('shopping.editCategory', { categoryName }),
    delete: (categoryName) => t('shopping.deleteCategory', { categoryName }),
  }

  return (
    <CategoryManagerDialog
      categories={categories}
      copy={copy}
      idPrefix="shopping-category"
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
