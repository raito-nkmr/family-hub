import {
  createShoppingItemApiV1ShoppingGroupsGroupIdItemsPost,
  listShoppingItemsApiV1ShoppingGroupsGroupIdItemsGet,
  purchaseShoppingItemApiV1ShoppingItemsItemIdPurchasePost,
  restoreShoppingItemApiV1ShoppingItemsItemIdPurchaseDelete,
  addUnplannedShoppingPurchaseApiV1ShoppingTripsTripIdPurchasesPost,
  createShoppingCategoryApiV1ShoppingGroupsGroupIdCategoriesPost,
  createShoppingRequestApiV1ShoppingGroupsGroupIdRequestsPost,
  deleteShoppingCategoryApiV1ShoppingCategoriesCategoryIdDelete,
  deleteShoppingRequestApiV1ShoppingRequestsItemIdDelete,
  getShoppingStatisticsApiV1ShoppingGroupsGroupIdStatisticsGet,
  getShoppingTripApiV1ShoppingTripsTripIdGet,
  listShoppingCategoriesApiV1ShoppingGroupsGroupIdCategoriesGet,
  listShoppingRequestsApiV1ShoppingGroupsGroupIdRequestsGet,
  listShoppingTripsApiV1ShoppingGroupsGroupIdTripsGet,
  purchaseShoppingRequestApiV1ShoppingRequestsItemIdPurchasePost,
  reorderShoppingCategoriesApiV1ShoppingGroupsGroupIdCategoriesOrderPatch,
  reverseShoppingPurchaseApiV1ShoppingPurchasesPurchaseIdReversePost,
  startShoppingTripApiV1ShoppingGroupsGroupIdTripsPost,
  updateShoppingCategoryApiV1ShoppingCategoriesCategoryIdPatch,
  updateShoppingPurchaseApiV1ShoppingPurchasesPurchaseIdPatch,
  updateShoppingRequestApiV1ShoppingRequestsItemIdPatch,
  updateShoppingTripApiV1ShoppingTripsTripIdPatch,
  type ShoppingCategoryResponse,
  type ShoppingListItemResponse,
  type ShoppingItemResponse,
  type ShoppingPurchaseResponse,
  type ShoppingStatisticsResponse,
  type ShoppingTripListResponse,
  type ShoppingTripResponse,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'

export type ShoppingItem = ShoppingItemResponse
export type ShoppingRequest = ShoppingListItemResponse
export type ShoppingCategory = ShoppingCategoryResponse
export type ShoppingPurchase = ShoppingPurchaseResponse
export type ShoppingTrip = ShoppingTripResponse
export type ShoppingTripList = ShoppingTripListResponse
export type ShoppingStatistics = ShoppingStatisticsResponse

export async function getShoppingItems(groupId: string, signal?: AbortSignal): Promise<ShoppingItem[]> {
  return (await sdkData(listShoppingItemsApiV1ShoppingGroupsGroupIdItemsGet({ path: { group_id: groupId }, signal })))
    .items
}

export function createShoppingItem(groupId: string, itemName: string): Promise<ShoppingItem> {
  return sdkData(
    createShoppingItemApiV1ShoppingGroupsGroupIdItemsPost({
      path: { group_id: groupId },
      body: { name: itemName },
    }),
  )
}

export function purchaseShoppingItem(itemId: string): Promise<ShoppingItem> {
  return sdkData(
    purchaseShoppingItemApiV1ShoppingItemsItemIdPurchasePost({
      path: { item_id: itemId },
    }),
  )
}

export function restoreShoppingItem(itemId: string): Promise<ShoppingItem> {
  return sdkData(
    restoreShoppingItemApiV1ShoppingItemsItemIdPurchaseDelete({
      path: { item_id: itemId },
    }),
  )
}

export async function getShoppingRequests(groupId: string, signal?: AbortSignal): Promise<ShoppingRequest[]> {
  return (
    await sdkData(listShoppingRequestsApiV1ShoppingGroupsGroupIdRequestsGet({ path: { group_id: groupId }, signal }))
  ).items
}

export function createShoppingRequest(
  groupId: string,
  body: { name: string; assignee_user_id?: string | null; category_id?: string | null },
): Promise<ShoppingRequest> {
  return sdkData(createShoppingRequestApiV1ShoppingGroupsGroupIdRequestsPost({ path: { group_id: groupId }, body }))
}

export function updateShoppingRequest(
  itemId: string,
  body: { name: string; assignee_user_id?: string | null; category_id?: string | null },
): Promise<ShoppingRequest> {
  return sdkData(updateShoppingRequestApiV1ShoppingRequestsItemIdPatch({ path: { item_id: itemId }, body }))
}

export function deleteShoppingRequest(itemId: string): Promise<void> {
  return sdkData(deleteShoppingRequestApiV1ShoppingRequestsItemIdDelete({ path: { item_id: itemId } }))
}

export async function getShoppingCategories(groupId: string, signal?: AbortSignal): Promise<ShoppingCategory[]> {
  return (
    await sdkData(
      listShoppingCategoriesApiV1ShoppingGroupsGroupIdCategoriesGet({ path: { group_id: groupId }, signal }),
    )
  ).items
}

export function createShoppingCategory(groupId: string, name: string): Promise<ShoppingCategory> {
  return sdkData(
    createShoppingCategoryApiV1ShoppingGroupsGroupIdCategoriesPost({ path: { group_id: groupId }, body: { name } }),
  )
}

export function updateShoppingCategory(categoryId: string, name: string): Promise<ShoppingCategory> {
  return sdkData(
    updateShoppingCategoryApiV1ShoppingCategoriesCategoryIdPatch({ path: { category_id: categoryId }, body: { name } }),
  )
}

export function deleteShoppingCategory(categoryId: string): Promise<void> {
  return sdkData(deleteShoppingCategoryApiV1ShoppingCategoriesCategoryIdDelete({ path: { category_id: categoryId } }))
}

export async function reorderShoppingCategories(groupId: string, categoryIds: string[]): Promise<ShoppingCategory[]> {
  return (
    await sdkData(
      reorderShoppingCategoriesApiV1ShoppingGroupsGroupIdCategoriesOrderPatch({
        path: { group_id: groupId },
        body: { category_ids: categoryIds },
      }),
    )
  ).items
}

export function startShoppingTrip(groupId: string): Promise<ShoppingTrip> {
  return sdkData(startShoppingTripApiV1ShoppingGroupsGroupIdTripsPost({ path: { group_id: groupId } }))
}

export function purchaseShoppingRequest(itemId: string, tripId?: string): Promise<ShoppingPurchase> {
  return sdkData(
    purchaseShoppingRequestApiV1ShoppingRequestsItemIdPurchasePost({
      path: { item_id: itemId },
      query: tripId ? { trip_id: tripId } : undefined,
    }),
  )
}

export async function getShoppingTrips(
  groupId: string,
  cursor?: string,
  signal?: AbortSignal,
  limit?: number,
): Promise<ShoppingTripList> {
  return sdkData(
    listShoppingTripsApiV1ShoppingGroupsGroupIdTripsGet({
      path: { group_id: groupId },
      query: cursor || limit ? { cursor, limit } : undefined,
      signal,
    }),
  )
}

export function getShoppingTrip(tripId: string, signal?: AbortSignal): Promise<ShoppingTrip> {
  return sdkData(getShoppingTripApiV1ShoppingTripsTripIdGet({ path: { trip_id: tripId }, signal }))
}

export function updateShoppingTrip(
  tripId: string,
  body: { total_amount_yen?: number | null; finalize?: boolean },
): Promise<ShoppingTrip> {
  return sdkData(updateShoppingTripApiV1ShoppingTripsTripIdPatch({ path: { trip_id: tripId }, body }))
}

export function addUnplannedShoppingPurchase(
  tripId: string,
  body: { name: string; category_id?: string | null; purchased_by_user_id?: string | null },
): Promise<ShoppingPurchase> {
  return sdkData(addUnplannedShoppingPurchaseApiV1ShoppingTripsTripIdPurchasesPost({ path: { trip_id: tripId }, body }))
}

export function updateShoppingPurchase(
  purchaseId: string,
  body: { category_id?: string | null; purchased_by_user_id?: string | null },
): Promise<ShoppingPurchase> {
  return sdkData(
    updateShoppingPurchaseApiV1ShoppingPurchasesPurchaseIdPatch({ path: { purchase_id: purchaseId }, body }),
  )
}

export function reverseShoppingPurchase(purchaseId: string): Promise<ShoppingPurchase> {
  return sdkData(
    reverseShoppingPurchaseApiV1ShoppingPurchasesPurchaseIdReversePost({ path: { purchase_id: purchaseId } }),
  )
}

export function getShoppingStatistics(
  groupId: string,
  fromDate: string,
  toDate: string,
  signal?: AbortSignal,
): Promise<ShoppingStatistics> {
  return sdkData(
    getShoppingStatisticsApiV1ShoppingGroupsGroupIdStatisticsGet({
      path: { group_id: groupId },
      query: { from_date: fromDate, to_date: toDate },
      signal,
    }),
  )
}
