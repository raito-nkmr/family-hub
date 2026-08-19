# データベース設計

English version: [database-design.md](./database-design.md)

## 目的

この文書では、Family Hubの写真、掃除、買い物に関するPostgreSQLのスキーマ、制約、インデックス、マイグレーション方針を定義する。
画像ファイルは内蔵の写真ストレージHDDに保存し、PostgreSQLには検索と整合性検査に必要なメタデータを保存する。
各原本と同じUUIDを持つJSONサイドカーも復旧用として内蔵HDDに保存する。接続を解除した外付けHDDには、原本とDBバックアップの世代スナップショットを保存する。

開発DBはベースライン変更時にリセットするため、現在のアプリケーションスキーマは1つのベースラインへ統合している。
今後承認されたスキーマ変更は新しいマイグレーションとして追加する。人物検出など将来機能のテーブルは、機能が承認され要件が決まるまで作成しない。

```text
family_groups 1 ───── 0..N albums 1 ───── 0..N album_photos N..0 ───── 1 photos
photos 1 ───── 1 photo_metadata
photos 1 ───── 0..N photo_derivatives
photos 1 ───── 0..N photo_shares N..1 ───── 1 family_groups
users 1 ───── 0..N photo_favorites N..1 ───── 1 photos
photos 1 ───── 0..N photo_activity_events 1 ───── 1..N photo_activity_event_groups N..1 ───── 1 family_groups
users 1 ───── 0..1 photo_activity_states
users 1 ───── 0..N family_group_members N..1 ───── 1 family_groups
family_groups 1 ───── 0..N cleaning_tasks 1 ───── 0..N cleaning_completions
family_groups 1 ───── 0..N shopping_items
users 1 ───── 0..N upload_batches 1 ───── 1..N upload_items N..0 ───── 0..1 photos
upload_batches 1 ───── 0..N upload_batch_group_shares N..1 ───── 1 family_groups
users 1 ───── 0..N push_subscriptions N..1 ───── 1 user_sessions
users 1 ───── 0..N notification_preferences
users 1 ───── 0..N notification_outbox 1 ───── 0..N notification_deliveries
push_subscriptions 1 ───── 0..N notification_deliveries
maintenance_runs
administrative_audit_events
```

この図は現在のスキーマだけを示す。未実装の提案は`proposals/`に置き、現在のリレーショナル契約には含めない。

## 共通方針

- 主キーにはPostgreSQLの`UUID`を使用する
- 一時ファイル、原本、DB行を書き込む前にPythonでUUID v4を生成する
- タイムスタンプはUTCの`TIMESTAMPTZ`で保存し、PostgreSQLのセッションタイムゾーンをUTCにする
- FastAPIはUTCのISO 8601タイムスタンプを返し、DB/API境界ではJSTへ変換しない
- Reactが表示値を`Asia/Tokyo`へ明示的に変換し、日付検索とグループ化にもJSTの日付境界を使う
- 写真の整理には`captured_at`を優先し、撮影日時がない場合だけ`uploaded_at`へフォールバックする
- 画像データ、絶対HDDパス、環境固有のマウントポイントをPostgreSQLへ保存しない
- 制約とインデックスにはAlembicで管理する安定した名前を付ける
- 当面はPostgreSQL固有のENUMを避け、変更しやすい文字列と`CHECK`制約を使う

`updated_at`という名前の列はINSERT時だけサーバー既定値を使う。アプリケーションserviceが対応する更新のたびに明示的に設定し、
スキーマに汎用更新トリガーは使用しない。

## 日時

DBとAPIの値はUTC、ユーザー向けの値はJSTとする。

```text
PostgreSQL  2026-07-14 03:00:00+00
FastAPI     2026-07-14T03:00:00Z
React       July 14, 2026 12:00 JST
```

サーバーが`uploaded_at`を生成する。オフセット付きのEXIF撮影時刻は、そのオフセットを使って変換する。
オフセットのないEXIF値はJSTとして解釈してからUTCへ変換する。欠落または無効なEXIF値は`captured_at`をnullにする。
Reactは`Intl.DateTimeFormat`などへ`Asia/Tokyo`を明示的に渡す。JSTの日付範囲はDBへ送る前にUTCへ変換し、深夜のJST区間も正しく含める。

## コアテーブル

### `users`

管理コマンドまたは管理者招待から作成された家族ユーザーを保存する。公開登録画面は提供しない。

| 列 | 型 | Null | 制約・目的 |
| --- | --- | --- | --- |
| `id` | `UUID` | No | アプリケーションが生成する主キー |
| `username` | `VARCHAR(64)` | No | NFKC・大文字小文字正規化済みのUnicodeユーザー名。unique |
| `password_hash` | `TEXT` | No | Argon2idハッシュ。平文は保存しない |
| `is_active` | `BOOLEAN` | No | falseの場合はログインと既存セッションの利用を拒否 |
| `system_role` | `VARCHAR(16)` | No | `admin`または`user` |
| `must_change_password` | `BOOLEAN` | No | 運用管理者のパスワードリセットで設定し、本人の変更後に解除 |
| `created_at` | `TIMESTAMPTZ` | No | 作成日時 |
| `password_changed_at` | `TIMESTAMPTZ` | No | これより前のセッションを無効化 |

`ck_users_username_lowercase`は、1〜64文字のUnicodeの文字または数字と`.`, `_`, `-`だけを許可する。
グループ権限は`system_role`から独立し、招待受諾では常に`user`を作成する。

### `user_invitations`

システム管理者が発行する一度だけのアカウント招待を保存する。正規化した予約ユーザー名、一意なSHA-256トークンハッシュ、作成者、作成・失効日時、
任意の使用日時と取消日時を含む。ユーザー名ごとに未使用かつ取消されていない招待は1件だけ許可する。
受諾時は行をロックし、期限、使用済み、取消済み、ユーザー名の一意性を検証してから、同じトランザクションでユーザーを作成し`used_at`を設定する。
生トークンは一度だけ返し、保存しない。同じユーザー名への置き換え招待を作成する場合は、期限切れを含む以前の未使用招待を同じトランザクション内で取消してから新しい招待を挿入する。

### `user_sessions`

サーバー側セッションを保存する。Cookieの生トークンは保存せず、小文字化したSHA-256ハッシュだけを一意な`token_hash`列へ保存する。
セッションに結び付いたCSRFトークン、作成時刻、最終使用時刻、絶対有効期限、任意の失効時刻も保存する。`expires_at`は`created_at`より後でなければならない。
全セッションを効率よく失効できるよう、`user_id`へ`ix_user_sessions_user_id`インデックスを付ける。

### `family_groups`

グローバルに一意な名前、作成者、作成時刻、更新時刻を持つ家族共有範囲を保存する。作成者検索用に`created_by_user_id`へインデックスを付ける。

### `family_group_members`

ユーザーとグループの多対多関係、およびグループ内の`admin`または`member`権限を保存する。複合主キーは`(group_id, user_id)`とし、`user_id`へインデックスを付ける。
グループと作成者の管理者メンバーシップは1トランザクションで作成する。メンバーシップや権限の変更中はグループをロックし、最後の有効な管理者の降格・削除をコミット前に拒否する。

### `family_group_membership_invitations`

グループ管理者が有効な既存ユーザーへ送る招待を保存する。グループ、招待対象、招待者、提案する権限、`pending`・`accepted`・`rejected`状態、作成・応答時刻を含む。
グループとユーザーの保留中招待は1件だけ許可する。受諾時は同じトランザクションでメンバーシップを作成し、グループ削除時はカスケードする。

## 掃除・買い物テーブル

### `cleaning_tasks`

グループ単位の掃除箇所と日数間隔を保存する。`interval_days`は1〜3650、`is_active`の既定値はtrueとし、作成者とタイムスタンプを保持する。
`(group_id, is_active)`へ`ix_cleaning_tasks_group_id_is_active`を付ける。カウントダウンや`next_due_at`は保存せず、最新の完了または`created_at`に間隔を加えて計算する。
停止は論理状態の変更であり、履歴を保持する。

### `cleaning_completions`

タスク、完了ユーザー、サーバー生成のUTC時刻を持つ追記専用の完了履歴を保存する。`(task_id, completed_at DESC, id DESC)`へ
`ix_cleaning_completions_task_id_completed_at`を付ける。同時実行された完了も両方保持し、最新時刻とUUIDで次回期限を決める。履歴の編集・削除は範囲外とする。

### `shopping_items`

グループの品目、作成者、任意の購入者、作成・更新時刻、任意の購入時刻を保存する。購入者と購入時刻は両方nullか、両方設定済みでなければならない。
`(group_id, purchased_at, created_at)`へ`ix_shopping_items_group_id_purchase_state`を付ける。未購入品は`created_at ASC, id ASC`、
購入済みは`purchased_at DESC, id DESC`で一覧する。購入状態の変更中は行をロックし、未購入へ戻すときは購入者と時刻を消去する。

## 写真テーブル

### `photos`

原本1件につき1つのメタデータ行を保存する。重要な列はアップロード者とユーザー名のスナップショット、表示ファイル名、相対`storage_key`、
検証済みコンテンツタイプ、正のサイズ、小文字のSHA-256、サイズ、撮影・アップロード時刻、ライフサイクル状態（`active`、`trashed`、`purge_pending`）、
ゴミ箱・完全削除の時刻と所有者である。同じ行で画像と対応動画を表し、`content_type`で区別し、サイズは動画ストリームにも設定する。

制約には一意な`storage_key`、存在する所有者、`(uploaded_by_user_id, sha256)`の一意性、正のサイズ、小文字64文字のSHA-256、
両方設定または両方nullのサイズ、正しいライフサイクルと時刻の組み合わせを含める。許可するメディア形式をDBの`CHECK`へ含めず、
アップロードと復旧時にMIMEタイプとファイル内容を検証する。対応メディアはJPEG、MPOから選択した主画像、PNG、HEIF/HEIC、MP4、QuickTime MOV、M4Vである。

### `photo_metadata`

ユーザー編集可能な情報を原本メタデータから分離する。`photo_id`をキーとし、最大2,000文字のメモ、任意の所有者入力`captured_at_override`、
メモの編集者と最終編集時刻、楽観的ロック用`version`、タイムスタンプを保存する。実効撮影時刻は、設定されていれば`captured_at_override`、
なければ原本の`photos.captured_at`とする。閲覧者は共有メモを編集できるが、共有先や撮影時刻の上書きを編集できるのは所有者だけである。
メタデータ更新のたびにversionを増やし、JSONサイドカーの`metadata_version`と同期する。

### `photo_derivatives`

再生成可能な表示ファイルを保存し、最初は写真ごとに1枚のサムネイルを持つ。ID、写真ID、種類（`thumbnail`）、相対派生`storage_key`、
コンテンツタイプ（`image/webp`）、正のサイズ、作成時刻を持つ。写真削除時はカスケードし、storage keyは一意とする。

### `photo_shares`

写真と家族グループを関連付ける。写真・グループの複合キーで重複を防ぐ。一覧と詳細の認可では所有者または現在のグループメンバーシップを確認し、アルバムだけではアクセス権を与えない。

### `photo_favorites`

ユーザーと写真の組み合わせ、および作成時刻を保存する。お気に入りは共有、アルバム、他のユーザーから独立する。

### 活動テーブル

`photo_activity_events`は`uploaded`または`shared`、写真、操作ID、発生時刻を記録する。バッチアップロードと一括共有には同じ操作IDを使い、新着でまとめて表示できるようにする。
個別操作にもIDを付与する。`photo_activity_event_groups`はイベント時点でアクセス権を得たグループを記録する。
取得時は、現在のメンバーシップ、イベントより前のメンバーシップ開始、現在も有効な共有を確認し、参加前と後から共有解除されたイベントを除外する。

`photo_activity_states`は各ユーザーの`(seen_through_at, seen_through_event_id)`既読位置を保存する。未読イベントはその組より新しく、かつ現在ユーザーに見えるものとする。
カーソルページネーションには`(occurred_at DESC, id DESC)`を使用する。

## 一覧用インデックスと検索

写真は撮影時刻を優先し、なければアップロード時刻で並べる。

```sql
SELECT *
FROM photos
ORDER BY COALESCE(captured_at, uploaded_at) DESC, id DESC;

CREATE INDEX ix_photos_sort_date_id
    ON photos (COALESCE(captured_at, uploaded_at) DESC, id DESC);
```

カーソルには日付とUUIDの組を保存し、最後の組より小さい行を最大100件取得する。ファイル名とメモの部分一致検索には`pg_trgm`のGINインデックスを使う。

```sql
CREATE INDEX ix_photos_original_filename_trgm
    ON photos USING gin (original_filename gin_trgm_ops);
CREATE INDEX ix_photo_metadata_memo_trgm
    ON photo_metadata USING gin (memo gin_trgm_ops);
```

`COALESCE(captured_at, uploaded_at)`を`Asia/Tokyo`へ変換して月と日付の境界を扱うが、保存時刻はUTCのままにする。一意制約が提供するインデックスを重複して作成しない。

## アップロードテーブルとトランザクション

`upload_batches`はブラウザのバッチ所有者、`active`・`completed`・`canceled`状態、作成時刻、再開期限、完了時刻を保存する。
`(owner_user_id, created_at DESC)`へインデックスを付ける。期限切れのactiveバッチは次のアクセスまたは作成時にcanceledへ変更し、`.part`ファイルを削除する。
APIの`visibility`は保存せず、共有グループが0個か1個以上かから導出する。各ファイルの完了時に所有者のグループメンバーシップを再確認する。

`upload_batch_group_shares`は、確定するすべての写真へ適用する一意な`(batch_id, group_id)`共有集合を保存する。

`upload_items`はブラウザの`client_id`、原ファイル名、申告コンテンツタイプ、期待・受信バイト数、`queued`・`uploading`・`processing`・`succeeded`・
`duplicate`・`failed`状態、安定したエラーコード、任意の写真ID、タイムスタンプを保存する。`(batch_id, client_id)`は一意とし、受信バイト数は0からサイズまでとする。
ファイルは独立して完了し、1件の失敗が成功済み写真をロールバックしない。

各チャンク後に`received_bytes`をcommitし、中断後に`.part`サイズと照合できるようにする。受信後は項目を`processing`としてcommitし、原本、サイドカー、WebPサムネイルを確定する。
その後、`photos`、`photo_metadata`、`photo_derivatives`、必要な共有、活動行を1トランザクションで挿入する。再試行を冪等にするため`UploadItem.id`を`Photo.id`として使う。

```text
HDD上で原本を確定
  ↓
HDD上でJSONサイドカーを確定
  ↓
内蔵SSD上でWebPサムネイルを確定
  ↓
photos、photo_metadata、photo_derivatives、photo_sharesを挿入
  ↓
共有時は活動イベントと対象グループを挿入
  ↓
1つのDBトランザクションをcommit
```

commitが失敗した場合は確定済みファイルの削除を試みる。復旧不能なファイルは整合性復旧候補とする。ファイルrenameとDB commitは1トランザクションにできないため、
保守検査で途中状態の原本、サイドカー、サムネイル、未登録ファイル、ファイルを失ったDB行を検出する。

## アルバムとファイルの対応

`albums`はタイトル、任意の説明、グループ、表紙写真、作成者のスナップショット、タイムスタンプを保存する。名前は一意でなくてよい。
グループのメンバーがアルバムを閲覧・編集できる。`updated_at DESC, id DESC`で一覧し、`album_photos`を数える。

`album_photos`の複合主キーは`(album_id, photo_id)`で、`added_at`を持つ。`photo_id`へインデックスを付け、アルバム内写真は
`COALESCE(captured_at, uploaded_at) ASC, photos.id ASC`で並べる。表紙未設定時は追加日時が最も古い写真へフォールバックする。
表紙はアルバム所属写真でなければならず、写真を外すと表紙も解除する。グループ共有を解除すると、同じトランザクションでアクセスできなくなったアルバム関連も削除する。
アルバム関連はJSONサイドカーへ書き込まない。

相対キーだけを保存する。例:

```text
originals/2026/07/550e8400-e29b-41d4-a716-446655440000.jpg
```

`YYYY/MM`は撮影時刻ではなくアップロード時刻を基準にする。撮影メタデータを変更しても原本を移動しない。パス作成に`original_filename`を使用しない。
受け付けたJPEG、MPOの主画像、PNG、HEIF/HEIC、MP4、QuickTime MOV、M4Vのバイト列は再圧縮・形式変換せず保存する。
`content_type`だけを信用せず、アップロードと復旧時に実際の内容を検証する。動画サムネイルは再生成可能な先頭フレームWebP派生画像であり、動画変換やストリーミング最適化はこの実装の範囲外である。

## JSONサイドカー

各原本の横に同じUUIDのJSONファイルを1つ保存する。サイドカーは復旧情報であり、通常の一覧や検索の正本ではない。
スキーマバージョン6では、原本・派生アセット、編集可能メタデータ、共有を分離する。

| フィールド | 目的 |
| --- | --- |
| `schema_version` | サイドカー形式のバージョン |
| `id` | `photos.id`と原本ファイル名で共有するUUID |
| `metadata_version` | `photo_metadata.version`と一致する値 |
| `asset` | アップロード者、原本の詳細、サイズ、時刻、派生画像 |
| `metadata` | 共有メモ、最終編集者、最終編集時刻 |
| `sharing` | 家族グループIDの配列 |

復旧時はUUIDとパスの対応を確認し、原本からサイズ、ハッシュ、MIMEタイプ、サイズを再計算する。
`captured_at`は補正済みサイドカー値を使い、欠落または無効な場合だけEXIFへフォールバックする。
置き換えJSONは`.part`へ書き込んでrenameしてから、DBとサイドカーメタデータを更新する。整合性検査用にサムネイルの場所を含めるが、人物解析結果など他の再生成可能な派生データは含めない。

## 保守・通知テーブル

`maintenance_runs`はジョブ種別、状態、開始・終了時刻、構造化サマリー、秘密でない失敗理由を保存する。
`administrative_audit_events`は管理対象範囲、実行者IDとユーザー名のスナップショット、対象、秘密でないJSON詳細、時刻を保存する。
実行者やグループへの外部キーを意図的に持たず、物理削除後も監査行を残す。

`push_subscriptions`はエンドポイントと暗号鍵をユーザーおよびログインセッションへ関連付ける。`(user_sessions.id, user_sessions.user_id)`への複合外部キーにより、
あるユーザーの購読を別ユーザーのセッションへ結び付けることを防ぐ。`notification_preferences`はユーザーごとの写真共有、掃除期限、買い物追加の設定を保存する。
`notification_outbox`は受信者と重複排除キーを一意に持ち、業務操作と同じトランザクションで作成する。`claimed_at`と`claim_token`はworkerの所有を追跡する。
`notification_deliveries`はoutbox・購読の組を複合キーとして、端末ごとの試行回数、状態、完了時刻、秘密でないエラーコードを保存する。

## 将来スキーマとマイグレーション方針

要件が承認されるまで、人物検出、タグ、顔認識、シーン分類のテーブルを追加しない。暫定的な人物検出モデルは
[`proposals/person-detection.md`](./proposals/person-detection.md)にある。

初期開発履歴はベースライン`20260715_01`へリセット・統合した。このベースラインは認証、写真、アルバム、グループ、招待、再開可能アップロード、掃除のスキーマを作成する。
その後の変更は独立したマイグレーションとし、ベースラインを書き換えない。以降、派生画像、ファイル名・メモ検索用`pg_trgm`、買い物、メモ編集メタデータ、
お気に入りとアルバムグループ、活動イベントと既読位置、ゴミ箱ライフサイクル、保守履歴、Push購読とoutbox、端末別配信状態、グループ名の一意性、
監査イベント、グループメンバー招待、運用リセット用の強制パスワード変更フラグなどを、`20260723_13`以降の現在のrevisionまで追加している。

開発DBはリセットできるため、ローカルのダミーデータだけを保持する目的で互換性用のbackfillを追加しない。実データのある環境では、明示的なbackfillとdowngradeまたは復元手順が必要である。
アプリケーション起動時に`create_all()`でスキーマを暗黙作成せず、すべてのスキーマ変更を管理された単位で適用・ロールバックできるAlembicマイグレーションにする。

日本語版: [database-design.ja.md](./database-design.ja.md)
