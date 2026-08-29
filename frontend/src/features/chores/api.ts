import {
  completeChoreTaskApiV1ChoresTasksTaskIdCompletionsPost,
  createChoreCategoryApiV1ChoresGroupsGroupIdCategoriesPost,
  createChoreTaskApiV1ChoresGroupsGroupIdTasksPost,
  deleteChoreCategoryApiV1ChoresCategoriesCategoryIdDelete,
  getChoreMonthlyReportApiV1ChoresGroupsGroupIdReportsMonthlyGet,
  listChoreCategoriesApiV1ChoresGroupsGroupIdCategoriesGet,
  listChoreTasksApiV1ChoresGroupsGroupIdTasksGet,
  reorderChoreCategoriesApiV1ChoresGroupsGroupIdCategoriesOrderPatch,
  updateChoreCategoryApiV1ChoresCategoriesCategoryIdPatch,
  updateChoreTaskApiV1ChoresTasksTaskIdPatch,
  type ChoreCategoryResponse,
  type ChoreMonthlyReportResponse,
  type ChoreTaskResponse,
  type ChoreTaskUpdate,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'

export type ChoreTask = ChoreTaskResponse
export type ChoreCategory = ChoreCategoryResponse
export type ChoreMonthlyReport = ChoreMonthlyReportResponse
export type ChoreTaskChanges = ChoreTaskUpdate

export async function getChoreCategories(groupId: string, signal?: AbortSignal): Promise<ChoreCategory[]> {
  return (
    await sdkData(listChoreCategoriesApiV1ChoresGroupsGroupIdCategoriesGet({ path: { group_id: groupId }, signal }))
  ).items
}

export function createChoreCategory(groupId: string, categoryName: string): Promise<ChoreCategory> {
  return sdkData(
    createChoreCategoryApiV1ChoresGroupsGroupIdCategoriesPost({
      path: { group_id: groupId },
      body: { name: categoryName },
    }),
  )
}

export function updateChoreCategory(categoryId: string, categoryName: string): Promise<ChoreCategory> {
  return sdkData(
    updateChoreCategoryApiV1ChoresCategoriesCategoryIdPatch({
      path: { category_id: categoryId },
      body: { name: categoryName },
    }),
  )
}

export function deleteChoreCategory(categoryId: string): Promise<void> {
  return sdkData(
    deleteChoreCategoryApiV1ChoresCategoriesCategoryIdDelete({
      path: { category_id: categoryId },
    }),
  )
}

export async function reorderChoreCategories(groupId: string, categoryIds: string[]): Promise<ChoreCategory[]> {
  return (
    await sdkData(
      reorderChoreCategoriesApiV1ChoresGroupsGroupIdCategoriesOrderPatch({
        path: { group_id: groupId },
        body: { category_ids: categoryIds },
      }),
    )
  ).items
}

export async function getChoreTasks(groupId: string, signal?: AbortSignal): Promise<ChoreTask[]> {
  return (await sdkData(listChoreTasksApiV1ChoresGroupsGroupIdTasksGet({ path: { group_id: groupId }, signal }))).items
}

export function createChoreTask(
  groupId: string,
  taskName: string,
  intervalDays: number,
  categoryId: string,
): Promise<ChoreTask> {
  return sdkData(
    createChoreTaskApiV1ChoresGroupsGroupIdTasksPost({
      path: { group_id: groupId },
      body: { task_name: taskName, interval_days: intervalDays, category_id: categoryId },
    }),
  )
}

export function updateChoreTask(taskId: string, changes: ChoreTaskChanges): Promise<ChoreTask> {
  return sdkData(
    updateChoreTaskApiV1ChoresTasksTaskIdPatch({
      path: { task_id: taskId },
      body: changes,
    }),
  )
}

export function completeChoreTask(taskId: string): Promise<ChoreTask> {
  return sdkData(
    completeChoreTaskApiV1ChoresTasksTaskIdCompletionsPost({
      path: { task_id: taskId },
    }),
  )
}

export function getChoreMonthlyReport(
  groupId: string,
  month: string,
  signal?: AbortSignal,
): Promise<ChoreMonthlyReport> {
  return sdkData(
    getChoreMonthlyReportApiV1ChoresGroupsGroupIdReportsMonthlyGet({
      path: { group_id: groupId },
      query: { month },
      signal,
    }),
  )
}
