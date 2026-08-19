import { RefreshButton } from './RefreshButton'

export interface GroupScopedToolbarProps {
  groups: ReadonlyArray<{ id: string; name: string }>
  selectedGroupId: string | null
  selectId: string
  label: string
  selectDisabled: boolean
  refreshDisabled: boolean
  onSelectGroup: (groupId: string) => void | Promise<void>
  onRefresh: () => void | Promise<void>
}

export function GroupScopedToolbar({
  groups,
  selectedGroupId,
  selectId,
  label,
  selectDisabled,
  refreshDisabled,
  onSelectGroup,
  onRefresh,
}: GroupScopedToolbarProps) {
  return (
    <div className="group-scoped-toolbar">
      <div>
        <label htmlFor={selectId}>{label}</label>
        <select
          id={selectId}
          value={selectedGroupId ?? ''}
          disabled={selectDisabled}
          onChange={(event) => void onSelectGroup(event.target.value)}
        >
          {groups.map((group) => (
            <option key={group.id} value={group.id}>
              {group.name}
            </option>
          ))}
        </select>
      </div>
      <RefreshButton disabled={refreshDisabled} onClick={onRefresh} />
    </div>
  )
}
