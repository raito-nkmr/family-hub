import { CategoryIcon } from './icons'

export interface CategoryFilterOption {
  id: string
  name: string
}

interface CategoryFilterToolbarProps<T extends CategoryFilterOption> {
  categories: readonly T[]
  selectedCategory: string
  allCategoryValue?: string
  allLabel: string
  ariaLabel: string
  manageLabel: string
  manageDisabled: boolean
  noCategory?: {
    value: string
    label: string
  }
  onSelectCategory: (categoryId: string) => void
  onManage: () => void
}

export function CategoryFilterToolbar<T extends CategoryFilterOption>({
  categories,
  selectedCategory,
  allCategoryValue = 'all',
  allLabel,
  ariaLabel,
  manageLabel,
  manageDisabled,
  noCategory,
  onSelectCategory,
  onManage,
}: CategoryFilterToolbarProps<T>) {
  return (
    <div className="category-toolbar">
      <nav className="category-filter" aria-label={ariaLabel}>
        <button
          className={`category-filter__button${selectedCategory === allCategoryValue ? ' category-filter__button--active' : ''}`}
          type="button"
          aria-pressed={selectedCategory === allCategoryValue}
          onClick={() => onSelectCategory(allCategoryValue)}
        >
          {allLabel}
        </button>
        {categories.map((category) => (
          <button
            className={`category-filter__button${selectedCategory === category.id ? ' category-filter__button--active' : ''}`}
            key={category.id}
            type="button"
            aria-pressed={selectedCategory === category.id}
            onClick={() => onSelectCategory(category.id)}
          >
            {category.name}
          </button>
        ))}
        {noCategory && (
          <button
            className={`category-filter__button${selectedCategory === noCategory.value ? ' category-filter__button--active' : ''}`}
            type="button"
            aria-pressed={selectedCategory === noCategory.value}
            onClick={() => onSelectCategory(noCategory.value)}
          >
            {noCategory.label}
          </button>
        )}
      </nav>
      <button className="secondary-button icon-button" type="button" disabled={manageDisabled} onClick={onManage}>
        <CategoryIcon />
        {manageLabel}
      </button>
    </div>
  )
}
