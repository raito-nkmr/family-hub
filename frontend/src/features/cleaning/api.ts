import {
  completeCleaningTaskApiV1CleaningTasksTaskIdCompletionsPost,
  createCleaningCategoryApiV1CleaningGroupsGroupIdCategoriesPost,
  createCleaningTaskApiV1CleaningGroupsGroupIdTasksPost,
  deleteCleaningCategoryApiV1CleaningCategoriesCategoryIdDelete,
  getCleaningMonthlyReportApiV1CleaningGroupsGroupIdReportsMonthlyGet,
  listCleaningCategoriesApiV1CleaningGroupsGroupIdCategoriesGet,
  listCleaningTasksApiV1CleaningGroupsGroupIdTasksGet,
  reorderCleaningCategoriesApiV1CleaningGroupsGroupIdCategoriesOrderPatch,
  updateCleaningCategoryApiV1CleaningCategoriesCategoryIdPatch,
  updateCleaningTaskApiV1CleaningTasksTaskIdPatch,
  type CleaningCategoryResponse,
  type CleaningMonthlyReportResponse,
  type CleaningTaskResponse,
  type CleaningTaskUpdate,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'

export type CleaningTask = CleaningTaskResponse
export type CleaningCategory = CleaningCategoryResponse
export type CleaningMonthlyReport = CleaningMonthlyReportResponse
export type CleaningTaskChanges = CleaningTaskUpdate

export async function getCleaningCategories(groupId: string, signal?: AbortSignal): Promise<CleaningCategory[]> {
  return (
    await sdkData(
      listCleaningCategoriesApiV1CleaningGroupsGroupIdCategoriesGet({ path: { group_id: groupId }, signal }),
    )
  ).items
}

export function createCleaningCategory(groupId: string, name: string): Promise<CleaningCategory> {
  return sdkData(
    createCleaningCategoryApiV1CleaningGroupsGroupIdCategoriesPost({
      path: { group_id: groupId },
      body: { name },
    }),
  )
}

export function updateCleaningCategory(categoryId: string, name: string): Promise<CleaningCategory> {
  return sdkData(
    updateCleaningCategoryApiV1CleaningCategoriesCategoryIdPatch({
      path: { category_id: categoryId },
      body: { name },
    }),
  )
}

export function deleteCleaningCategory(categoryId: string): Promise<void> {
  return sdkData(
    deleteCleaningCategoryApiV1CleaningCategoriesCategoryIdDelete({
      path: { category_id: categoryId },
    }),
  )
}

export async function reorderCleaningCategories(groupId: string, categoryIds: string[]): Promise<CleaningCategory[]> {
  return (
    await sdkData(
      reorderCleaningCategoriesApiV1CleaningGroupsGroupIdCategoriesOrderPatch({
        path: { group_id: groupId },
        body: { category_ids: categoryIds },
      }),
    )
  ).items
}

export async function getCleaningTasks(groupId: string, signal?: AbortSignal): Promise<CleaningTask[]> {
  return (await sdkData(listCleaningTasksApiV1CleaningGroupsGroupIdTasksGet({ path: { group_id: groupId }, signal })))
    .items
}

export function createCleaningTask(
  groupId: string,
  name: string,
  intervalDays: number,
  categoryId: string,
): Promise<CleaningTask> {
  return sdkData(
    createCleaningTaskApiV1CleaningGroupsGroupIdTasksPost({
      path: { group_id: groupId },
      body: { name, interval_days: intervalDays, category_id: categoryId },
    }),
  )
}

export function updateCleaningTask(taskId: string, changes: CleaningTaskChanges): Promise<CleaningTask> {
  return sdkData(
    updateCleaningTaskApiV1CleaningTasksTaskIdPatch({
      path: { task_id: taskId },
      body: changes,
    }),
  )
}

export function completeCleaningTask(taskId: string): Promise<CleaningTask> {
  return sdkData(
    completeCleaningTaskApiV1CleaningTasksTaskIdCompletionsPost({
      path: { task_id: taskId },
    }),
  )
}

export function getCleaningMonthlyReport(
  groupId: string,
  month: string,
  signal?: AbortSignal,
): Promise<CleaningMonthlyReport> {
  return sdkData(
    getCleaningMonthlyReportApiV1CleaningGroupsGroupIdReportsMonthlyGet({
      path: { group_id: groupId },
      query: { month },
      signal,
    }),
  )
}
