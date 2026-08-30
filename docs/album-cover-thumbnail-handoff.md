# Album cover thumbnail mismatch handoff

## Status

The frontend fix is implemented in the current worktree and now has a browser-level
regression test. The affected authenticated album was not inspected directly, so a
remaining mismatch in that browser should first be checked for a different or stale
frontend build because the React/CSS path tested here no longer has separate crops.

The user reports that, on an album detail page, the large cover image at the top
shows a different crop from the photo thumbnail in the album grid below. The
cover photo is the grid card marked `表紙`. The top image appears to crop more
towards the upper part of the photo, while the grid thumbnail shows a more
centered area. The user has restarted both the backend and frontend and tested
in the development environment.

The screenshot supplied by the user shows an album named `結婚式`. The top
image and the first grid card look like the same photo, but their visible
content is different.

## Repository and runtime state

- Repository: `/home/raito/Projects/family-hub`
- Branch: `dev`
- Branch is ahead of `origin/dev` by 7 commits.
- Current date during investigation: 2026-08-30 (Asia/Tokyo).
- `secrets/memo.md` and environment files were not inspected.
- The current album-thumbnail refactor is uncommitted.
- There are also unrelated pre-existing uncommitted changes in
  `backend/app/features/groups/router.py`,
  `backend/app/features/groups/schemas.py`, and
  `backend/app/features/groups/service.py`. Preserve them and do not include
  or reset them while investigating this issue.

Local processes observed during the investigation:

- Development backend: workspace `backend/.venv/bin/python -m uvicorn`, port `18000`.
- Development Vite server: workspace `frontend/node_modules/.bin/vite`, port `15173`.
- A separate production backend process exists on port `8000`, running from
  `/opt/family-hub/current`; it was started earlier and may not represent the
  current workspace. If the browser is using the production reverse proxy or
  port 8000, it is not necessarily testing the current development frontend.

## Relevant commits already made

These commits are already on `dev`:

- `af2514c fix: align album cover thumbnail ratio`
  - Changed the album list cover frame from fixed `88x72` to a `4 / 3` aspect
    ratio.
- `7b9fdf4 fix: align album cover thumbnail rendering`
  - Changed the album detail header cover from a direct `<img>` to the shared
    `PhotoPreview` thumbnail renderer.
  - Resolves the cover photo object from `album.photos` when available.
  - Added a test asserting that the header cover URL matches the first grid
    thumbnail URL.
  - Added `align-self: start` to the album list cover frame.
- `907094f fix: support tablet photo navigation taps`
  - Unrelated tablet photo-modal navigation fix.
- `5669473 chore: harden production release checks`
  - Unrelated production release script/documentation changes.

## Implemented uncommitted change

The fix makes the album detail header and album photo grid use one component:

- `frontend/src/features/albums/components/AlbumPhotoThumbnail.tsx`
  - Renders a shared `4 / 3` thumbnail frame and `PhotoPreview` image.
  - Adds `data-photo-id` to the frame for runtime comparison.
- `frontend/src/features/albums/components/AlbumDetailView.tsx`
  - Uses `AlbumPhotoThumbnail` for the large header cover.
- `frontend/src/features/albums/components/AlbumPhotoGrid.tsx`
  - Uses `AlbumPhotoThumbnail` for every grid thumbnail.
- `frontend/src/features/albums/albums.css`
  - Uses the same image class for both locations:
    `width: 100%`, `height: 100%`, `object-fit: cover`,
    `object-position: center center`.
  - Removed the album-grid hover `transform: scale(1.025)` so the grid image
    does not have a different visible range while hovered.
- `frontend/src/features/albums/components/AlbumDetailView.test.tsx`
  - Asserts that the header cover frame and the grid frame for the cover photo
    have the same `data-photo-id` and thumbnail URL.
- `frontend/e2e/album-cover-layout.spec.ts`
  - Loads an album with a portrait cover through mocked API and thumbnail responses.
  - Runs in iPhone and iPad WebKit and verifies equal photo IDs, image URLs,
    natural dimensions, computed `object-fit`/`object-position`, transforms, and
    frame aspect ratios.

This change has not been committed yet.

## Important technical findings

### Frontend image source

`PhotoPreview` defaults to `source="thumbnail"`. For that source it renders:

```text
/api/v1/photos/{photo_id}/thumbnail
```

Both the header cover and the album grid currently go through the same
`PhotoPreview` component and therefore should request the same URL when their
photo IDs are equal.

The current relevant CSS is effectively:

```css
.album-photo-thumbnail {
  aspect-ratio: 4 / 3;
  overflow: hidden;
}

.album-photo-thumbnail__image {
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center center;
}
```

The header cover has the same `4 / 3` ratio, and the grid frame has the same
ratio. Therefore, if both elements use the same image URL, the same natural
image dimensions, and the same computed CSS, the browser cannot produce a
meaningfully different crop. The WebKit regression test now verifies those
conditions with actual computed browser layout values.

### Backend image source

There is no separate album-cover image endpoint. The backend uses the normal
photo thumbnail endpoint for both cases:

- `backend/app/features/photos/router.py`
  - `GET /api/v1/photos/{photo_id}/thumbnail`
- `backend/app/features/photos/access_service.py`
  - `PhotoAccessService.get_photo_thumbnail()` returns the stored thumbnail
    derivative.
- `backend/app/features/photos/thumbnails.py`
  - `generate_thumbnail()` applies EXIF orientation and resizes within a
    `480x480` bounding box while preserving aspect ratio.
  - It does not crop the image.

Album detail cover selection is handled by:

- `backend/app/features/albums/service.py`
  - `get_album()` returns active album photos ordered by effective capture time.
  - The returned cover ID is the explicit active cover, or the first added
    active photo as fallback.
- `frontend/src/features/albums/useAlbums.ts`
  - Combines the paginated detail pages and uses `cover_photo_id` for both the
    header and the `表紙` badge.

No backend code was changed for the latest thumbnail attempts because the
backend does not have a separate crop path for album covers.

## Checks already run

From `frontend/`:

- `npm run format`
- `npm run format:check`
- `npm run lint`
- `npm run test:run`
  - 83 test files passed.
  - 328 tests passed.
- `npm run build`
  - TypeScript build and Vite production build passed.

Additional checks for the current fix:

- `npx vitest run src/features/albums/components/AlbumDetailView.test.tsx`
  - 1 test file and 2 tests passed.
- `npx playwright test e2e/album-cover-layout.spec.ts`
  - Passed in iPhone WebKit and iPad WebKit.

The browser test compares computed layout values. A screenshot baseline was not
added because those values no longer show separate crop paths.

The current album files also pass targeted Prettier and ESLint checks, and a direct
Vite production build succeeds. The repository-wide frontend checks were attempted,
but concurrent group-membership work currently causes failures outside this change:

- `format:check`: `src/features/groups/GroupPage.test.tsx` is not formatted.
- `lint` and the TypeScript phase of `build`: `queryClient` is unused in
  `src/features/groups/GroupPage.tsx`.
- `test:run`: two `InviteGroupMemberDialog` tests still expect the previous
  invitation wording.

## If the mismatch remains in the affected browser

1. Confirm the browser is using the development Vite URL, normally
   `http://127.0.0.1:15173`, rather than a production URL backed by
   `/opt/family-hub/current`.

2. On the affected album page, inspect the DOM. The latest uncommitted code
   exposes the IDs directly:

   ```js
   const cover = document.querySelector(
     ".album-detail-header__cover[data-photo-id]",
   );
   const coverImage = cover?.querySelector("img");
   const coverId = cover?.dataset.photoId;
   const card = [
     ...document.querySelectorAll(
       ".album-photo-card__image-wrap[data-photo-id]",
     ),
   ].find((element) => element.dataset.photoId === coverId);
   const cardImage = card?.querySelector("img");
   console.log({
     coverId,
     coverSrc: coverImage?.currentSrc || coverImage?.src,
     cardId: card?.dataset.photoId,
     cardSrc: cardImage?.currentSrc || cardImage?.src,
     coverNaturalSize: [coverImage?.naturalWidth, coverImage?.naturalHeight],
     cardNaturalSize: [cardImage?.naturalWidth, cardImage?.naturalHeight],
     coverRect: coverImage?.getBoundingClientRect().toJSON(),
     cardRect: cardImage?.getBoundingClientRect().toJSON(),
     coverStyle: coverImage && {
       objectFit: getComputedStyle(coverImage).objectFit,
       objectPosition: getComputedStyle(coverImage).objectPosition,
       transform: getComputedStyle(coverImage).transform,
     },
     cardStyle: cardImage && {
       objectFit: getComputedStyle(cardImage).objectFit,
       objectPosition: getComputedStyle(cardImage).objectPosition,
       transform: getComputedStyle(cardImage).transform,
     },
   });
   ```

3. Interpret the result:

   - Different `coverId` and `cardId`: investigate the album API response,
     React Query cache, or the page/build currently being served.
   - Same IDs but different `coverSrc` and `cardSrc`: investigate stale frontend
     code, a service worker/cache, or an unexpected `PhotoPreview` version.
   - Same IDs and URLs but different computed styles or rectangles: inspect CSS
     loading/order and responsive layout at the affected viewport.
   - Same IDs, URLs, natural dimensions, computed styles, and rectangles: the
     mismatch is not being produced by the React/CSS paths shown here. Inspect
     the actual network response bytes for the thumbnail and verify that the
     screenshot is from the same browser URL and release.

4. Do not regenerate or overwrite user photo derivatives blindly. First prove
   that the affected header and card request different resources or that the
   stored derivative itself is wrong.
