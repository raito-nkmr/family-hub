# PWA通知の現状仕様

English version: [web-push.md](./web-push.md)

## 現在の結論

Family Hubには、通知許可を要求して`PushManager`の購読をバックエンドへ登録する設定UI、通知Outbox、配信Worker、
およびService Workerで通知を表示してアプリ内画面へ移動する処理が実装されている。利用者は「その他」からアカウント画面を
開き、この端末の通知を有効化・解除し、通知する内容を変更できる。

iPhoneとiPadでWeb Pushを利用するには、iOSまたはiPadOS 16.4以降でFamily Hubをホーム画面へ追加し、standaloneの
Webアプリとして起動する必要がある。さらに、アプリ内のボタンをタップするなどの直接操作を契機として通知許可とPush購読を
要求しなければならない。Family Hubはアカウント画面の「通知を有効にする」ボタンから、この直接操作を開始する。
通常のSafari表示でPush APIを利用できない場合は、ホーム画面への追加手順を表示する。

## 実装済みの流れ

実装済みのフローは次のとおりである。

1. production buildでブラウザが`/sw.js`をService Workerとして登録する。
2. 利用者がホーム画面からstandalone版Family Hubを起動し、通知を有効にするボタンを操作する。
3. フロントエンドが通知許可を要求し、公開VAPID鍵を使ってPush購読を作成する。
4. endpointと暗号鍵を`POST /api/v1/notifications/subscriptions`へ登録する。登録後は通知種別の設定を変更できる。
5. 写真共有や買い物追加のトランザクション、または掃除期限確認コマンドが通知Outboxを作成する。
6. `python -m app.commands.send_notifications`がOutboxを取得し、Web Push providerへ暗号化した通知を送る。
7. Service Workerの`push`イベントが通知を表示し、端末内の未確認件数を増やして対応端末のアプリアイコンへbadgeを表示する。
8. 利用者が通知を開くとbadgeをクリアし、既存のFamily Hub画面を対象画面へ移動して前面化する。開いている画面がなければ
   新しく開く。通常のアプリ起動時もbadgeをクリアする。

## 通知の種類と初期設定

| 種類 | Outboxを作る契機 | 受信候補 | 初期設定 | 通知から開く画面 |
| --- | --- | --- | --- | --- |
| 写真共有 | 共有先を指定したアップロード、または新しいグループへの共有追加 | 新しい共有先グループのメンバー。操作した本人を除く | 有効 | `/photos/new` |
| 掃除期限 | 有効な掃除が期限を迎えた状態で期限確認コマンドを実行 | 対象グループの全メンバー | 有効 | `/cleaning` |
| 買い物追加 | 未購入品目をグループへ追加 | 対象グループのメンバー。追加した本人を除く | 無効 | `/shopping` |

通知文は購読登録時の`en`または`ja`に応じた定型文で、写真名、掃除名、品目名などの内容は含めない。同じ操作について
同じ利用者へOutboxを重複登録しない。通知設定UIは3種類すべての有効状態をまとめて保存する。

## 購読とログインセッション

Push購読は利用者だけでなく、登録したログインセッションにも関連付ける。配信対象になるのは、有効な利用者に属し、失効、
絶対期限切れ、アイドル期限切れ、またはパスワード変更前のログインセッションではない購読だけである。PostgreSQLも、保存された購読の利用者が
保存されたセッションの所有者であることを強制する。ログアウトや
パスワード変更によってセッションが無効になった端末には送らない。

1利用者の購読数は`PUSH_MAX_SUBSCRIPTIONS_PER_USER`で制限し、既定値は10とする。購読解除APIは、現在の利用者かつ
現在のログインセッションに属する購読だけを削除する。providerが`404`または`410`を返した購読は、配信Workerが
失効済みとして削除する。

## 配信、再試行、および表示

写真共有と買い物追加は、本体変更と同じDBトランザクションでOutboxへ登録する。掃除期限は
`python -m app.commands.enqueue_due_cleaning_notifications`で確認し、同じ掃除と期限の組み合わせを重複登録しない。
配信用のsystemd timer定義は1分間隔、掃除期限確認用のtimer定義は1時間間隔である。ただし、本番RunbookではVAPID設定と
実機確認が完了するまで、これらの通知timerを有効にしない。

配信状態は購読端末ごとに保存する。一部端末だけが一時的に失敗した場合、成功済み端末へは再送せず、未成功の端末だけを
再試行する。再試行間隔はOutboxの試行回数に応じて指数的に延ばし、端末ごとの試行が5回に達した一時エラーは失敗として
終了する。配信対象の購読がない場合や利用者が該当通知を無効にしている場合、Outboxは処理済みになる。

Service WorkerはPush payloadからタイトル、本文、遷移先、および重複表示をまとめるtagを受け取り、利用者に見える通知を
直ちに表示する。通知クリック時に利用できる遷移先は同一originだけで、外部URL、認証情報を含むURL、または不正なURLは
アプリのルートへ置き換える。Badging API対応端末ではPush受信ごとに端末内の未確認件数を最大999まで加算し、ホーム画面の
アプリアイコンへ表示する。PWAの起動時または通知クリック時に件数をクリアする。この件数はサーバー側の未読状態ではなく、
端末ごとに最後にアプリを開いてから受信した通知数である。利用者がOS設定でbadge表示を無効にしている場合は表示されない。
現時点では通知アクションボタンおよび通知一覧の画面はない。

## APIと設定

通知APIはすべてログインを必要とし、変更APIはCSRF検証も必要とする。

| API | 用途 |
| --- | --- |
| `GET /api/v1/notifications/config` | Web Pushの利用可否、公開VAPID鍵、現在のセッションの購読ID、および通知設定を取得 |
| `POST /api/v1/notifications/subscriptions` | 現在のログインセッションへPush購読を登録 |
| `DELETE /api/v1/notifications/subscriptions/{id}` | 現在のログインセッションのPush購読を解除 |
| `PUT /api/v1/notifications/preferences` | 3種類すべての有効状態を利用者単位で更新 |

Web Pushは`PUSH_VAPID_PUBLIC_KEY`、`PUSH_VAPID_PRIVATE_KEY_FILE`、および`PUSH_VAPID_SUBJECT`がすべて設定された
場合だけ有効になる。秘密鍵はリポジトリ外のファイルへ置く。購読endpointはHTTPSに限定し、
`PUSH_ALLOWED_ENDPOINT_HOSTS`へ明示したprovider hostだけを受け付ける。購読APIはendpointへ通信せず、外向き通信は
配信Workerだけが行う。

## 検証状況と残作業

API登録、CSRF、endpoint allowlist、購読上限、設定スキーマ、ブラウザ購読の登録・解除、通知設定UI、通知対象の生成、
安全なクリック遷移、badge件数の正規化、およびWorkerのclaim・端末別再試行は自動テストがある。WorkerのPostgreSQL統合テストは
`TEST_DATABASE_URL`を設定した環境で実行する。

2026年7月20日に公開テスト環境でVAPIDを設定し、iPhoneのホーム画面PWAから購読を登録した。別ユーザーによる買い物追加を
契機として、Outbox、Web Push provider、Service Workerを通るバックグラウンド日本語通知とアプリアイコンbadgeを確認した。
Outboxと端末別deliveryはいずれも`sent`で、通知配送timerと掃除期限確認timerは`enabled`かつ`active`である。

追加の受入確認として次が残る。

- 通知クリックによる対象画面への遷移
- Focus適用時、およびiPhoneの端末設定から通知やbadgeを無効化した場合の挙動

Appleの現在の前提は、[Apple DeveloperのWeb Push資料](https://developer.apple.com/documentation/usernotifications/sending-web-push-notifications-in-web-apps-and-browsers)と
[WebKitのiOS/iPadOS向け説明](https://webkit.org/blog/13878/web-push-for-web-apps-on-ios-and-ipados/)を参照する。
