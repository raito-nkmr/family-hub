# Frontend

ホーム、写真、アルバム、家族グループ、家事タスク、買い物リスト、およびアカウント安全設定を提供する
Family Hubのフロントエンドです。
React、React Router、TanStack Query、TypeScript、Viteを使用します。

プロダクトの方針は[`../docs/product-brief.md`](../docs/product-brief.md)を参照してください。

## ディレクトリ構成

フロントエンドは機能単位でコードをまとめるFeature-based構成とします。

```text
src/
├── app/            # URL定義、権限ガード、および認証後のアプリシェル
├── app-shell.css  # アプリ枠、ヘッダー、ナビゲーション
├── features/
│   ├── auth/       # 認証API、ログイン、パスワード変更、およびセッション管理画面
│   ├── albums/     # アルバムAPI、一覧、編集、整理モードでの写真追加・複数解除
│   ├── chores/  # 家族グループ単位の家事タスクと完了管理
│   ├── groups/     # 家族グループAPI、一覧、メンバー管理
│   ├── home/       # 写真、家事タスク、および買い物を横断するホーム画面
│   ├── invitations/ # 管理者向け招待管理と招待受諾
│   ├── maintenance/ # 管理者向けストレージ・保守状態
│   ├── notifications/ # Web Push購読、端末設定、および通知設定
│   ├── photos/     # 写真API、写真一覧、アップロード、詳細表示
│   ├── privacy/    # 認証なしで閲覧できるプライバシーページ
│   ├── pwa/        # ホーム画面への追加案内とPWA起動状態
│   └── shopping/   # 家族グループ単位の買い物リスト
├── shared/         # 複数featureで共有するAPI基盤、表示部品、型、フォーマッター
│   └── api/generated/ # FastAPIのOpenAPIから生成する型・fetch client・SDK。直接編集しない
├── test/           # Vitestの共通セットアップ
├── App.tsx         # セッション復元、招待受付、テーマ、および公開画面の組み立て
└── styles.css      # グローバルCSSの読み込みエントリーポイント
public/
├── manifest.webmanifest # PWAマニフェスト
├── notification-target.js # Push通知の同一origin遷移検証
└── sw.js           # アプリシェルキャッシュとWeb Push通知
```

機能固有のコードは対応する`features/<feature>/`へ置き、複数featureから必要になるまでは`shared/`へ移動しません。
`styles.css`からアプリ共通、shared、および各featureのグローバルCSSを読み込みます。

画面URLは`src/app/routes.ts`を正本とし、React RouterのDeclarative modeで画面とURLを対応付けます。
認証後の共通データとレイアウトは`src/app/AuthenticatedApp.tsx`とその状態・ルート・オーバーレイ分割へ置き、管理者専用画面は
`src/app/routeGuards.tsx`のルートガードで保護します。ナビゲーションには`Link`または`NavLink`を使用し、
コンポーネントからHistory APIを直接操作しません。
認証後の各Pageは`React.lazy`で画面単位に読み込み、初回表示に不要な画面コードをメインバンドルへ含めません。
Homeと写真領域のPage向けprops接続は各featureのroute containerへ置き、アプリシェルへ画面固有の表示配線を
増やさない。写真モーダル、ページをまたぐアップロード、および未読badgeに必要な状態だけは認証後シェルで維持する。

APIから取得する共有データはTanStack Queryでキャッシュし、取得中・失敗・再取得を各画面で個別実装しません。
キャッシュキーは`src/shared/api/queryKeys.ts`へ集約します。ホーム、アルバム、グループ、家事タスク、買い物、招待、通知、
セッション、保守状態、および各写真画面は同じQueryキャッシュと無効化規則を使用します。選択中のグループ・アルバムと
写真検索条件はURLのsearch paramsへ
保存するため、再読み込み、戻る・進む、およびURL共有でも状態を維持します。入力値、ダイアログ、およびアップロード
キューのような画面固有の一時状態はReactのローカル状態で管理します。破壊的操作の確認には共通のアクセシブルな
確認Dialogを使用します。

スマートフォンでは、ページの先頭から一定量下へ引っ張って離すと、認証後シェルが現在表示中のQueryを再取得します。
ボタンや入力欄、ダイアログ上のスワイプ、および横方向のスワイプは更新操作として扱いません。

各featureのPageコンポーネントは表示とイベント接続を担当し、API通信を伴う状態遷移と副作用は同じfeatureの
`use*.ts` hookへ置きます。単純な表示用ローカル状態まで共通hookへ移動せず、画面の責務を読み取りにくくする
抽象化は追加しません。

写真状態は`features/photos/usePhotoLibraryData.ts`が一覧・検索・タイムライン・ストレージQueryを管理し、
`features/photos/usePhotoLibrary.ts`がそのデータと選択・詳細フック、メタデータ更新フックを画面向けに合成します。
`usePhotoUpload.ts`がバッチ作成、2並列の分割送信、ファイル別の進捗、中止、および失敗分の再試行を
それぞれ管理します。`usePhotoDashboard.ts`は両者を画面向けに合成するだけに留めます。写真以外の機能画面では
写真一覧とタイムラインを取得しません。
写真一覧、アルバム詳細、アルバムの写真追加画面、およびゴミ箱は、50件単位のカーソルページネーションを
`IntersectionObserver`で自動読み込みする無限スクロールとして表示します。通信失敗時は自動読み込みを停止し、
手動の再試行ボタンを表示します。
`IntersectionObserver`のフォールバックとしてスクロール時に監視要素の位置も直接確認し、iPhone Safariと
ダイアログ内スクロールでも追加取得を継続します。
スマートフォンの写真一覧はサムネイル中心とし、2列、3列、4列を切り替えられます。既定は3列で、選択値は
`localStorage`へ保存します。ファイル名、撮影日時、および形式は一覧へ常時表示せず、詳細画面で確認します。
詳細画面では原本を1枚ずつダウンロードでき、所有写真の選択モードでは最大100枚の原本をZIPへ直接書き出せます。
大容量のZIPをブラウザのJavaScriptメモリへ保持しないよう、書き出しは認証Cookieを伴う直接ダウンロードとします。

## セットアップ

```bash
npm ci
```

## 開発サーバー

```bash
npm run dev
```

## 検証

```bash
npm run check
```

`npm run check`はOpenAPI生成物の整合性、format、lint、Vitest、およびproduction buildを順に検証します。
テストを監視モードで実行する場合は`npm test`、1回だけ実行する場合は`npm run test:run`を使用します。
主要クライアントであるiPhone相当のWebKitスモークテストはPlaywrightで実行します。初回だけブラウザを導入してから
テストを実行してください。通常のE2Eは公開画面とAPI mockによる認証後主要ナビゲーションを検証する。
production PWA E2Eはbuildとpreview serverを使い、Service Worker登録とアプリシェルcacheを検証する。
CIではブラウザとOS依存ライブラリを自動導入します。

```bash
npx playwright install webkit
npm run test:e2e
npm run test:e2e:pwa
```

Service Workerはproduction buildでのみ登録されるため、PWAキャッシュとPush通知からの画面遷移はHTTPSの
production相当環境でも確認します。通知内の遷移先は同一originに限定します。

通常のブラウザ表示では、ホーム画面にiPhoneの「ホーム画面に追加」手順への案内を表示します。案内を閉じた状態は
`localStorage`へ保存しますが、「その他」から開くアカウント画面では再び手順を確認できます。ホーム画面からstandaloneで
起動している場合は、これらの追加案内を表示しません。iOS用のApple Touch IconとPWAマニフェスト用PNGアイコンも
`public/`で配信します。

Service WorkerにはWeb Push通知の表示と安全な同一originへのクリック遷移を実装しています。「その他」からアカウント画面を
開くと、現在の端末で通知を有効化・解除し、写真共有、家事タスクの期限、および買い物追加の通知設定を変更できます。iPhoneでは
ホーム画面からstandalone版を起動し、「通知を有効にする」ボタンからシステムの許可を行います。現在の実装範囲と配信フローは
[`../docs/web-push.md`](../docs/web-push.md)を参照してください。

リポジトリルートの`make check`では、バックエンドとフロントエンドの全検証をまとめて実行できます。

## APIクライアント

`src/shared/api/generated/`の型、fetch client、およびSDKはFastAPIのOpenAPIスキーマから生成します。
バックエンドのrouterまたはPydantic schemaを変更した場合は、次を実行して生成結果もコミットします。

```bash
npm run api:generate
```

生成ファイルは直接編集しません。`npm run api:check`と`make check`は、コミットされた型が現在のOpenAPIと一致する
ことを検証します。
標準的なJSON CRUDは生成SDKをfeature APIから呼び出し、HTTP statusは`ApiError`へ正規化します。写真の分割送信、
直接ダウンロード、および進捗通知のようにブラウザ通信を細かく制御する処理だけは専用実装を維持します。
生成SDKと専用fetchの共通transportは、変更系リクエストへ現在のCSRF tokenを自動付与します。
