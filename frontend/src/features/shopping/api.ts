import {
  createShoppingItemApiV1ShoppingGroupsGroupIdItemsPost,
  listShoppingItemsApiV1ShoppingGroupsGroupIdItemsGet,
  purchaseShoppingItemApiV1ShoppingItemsItemIdPurchasePost,
  restoreShoppingItemApiV1ShoppingItemsItemIdPurchaseDelete,
  type ShoppingItemResponse,
} from '../../shared/api/generated'
import { sdkData } from '../../shared/api/sdkClient'

export type ShoppingItem = ShoppingItemResponse

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
