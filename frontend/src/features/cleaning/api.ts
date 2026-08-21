import {
  completeCleaningTaskApiV1CleaningTasksTaskIdCompletionsPost,
  createCleaningTaskApiV1CleaningGroupsGroupIdTasksPost,
  listCleaningTasksApiV1CleaningGroupsGroupIdTasksGet,
  updateCleaningTaskApiV1CleaningTasksTaskIdPatch,
  type CleaningTaskCategory,
  type CleaningTaskResponse,
  type CleaningTaskUpdate,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'

export type CleaningTask = CleaningTaskResponse
export type { CleaningTaskCategory }
export type CleaningTaskChanges = CleaningTaskUpdate

export async function getCleaningTasks(groupId: string, signal?: AbortSignal): Promise<CleaningTask[]> {
  return (await sdkData(listCleaningTasksApiV1CleaningGroupsGroupIdTasksGet({ path: { group_id: groupId }, signal })))
    .items
}

export function createCleaningTask(
  groupId: string,
  name: string,
  intervalDays: number,
  category: CleaningTaskCategory,
): Promise<CleaningTask> {
  return sdkData(
    createCleaningTaskApiV1CleaningGroupsGroupIdTasksPost({
      path: { group_id: groupId },
      body: { name, interval_days: intervalDays, category },
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
