# Instagram Integration Setup

Актуально на 11 июня 2026. Инструкция рассчитана на текущий проект Axon CRM после пуша последних изменений: `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET` и `INSTAGRAM_VERIFY_TOKEN` не нужно добавлять в `.env`; они сохраняются через CRM в `Settings -> Integrations -> Instagram`.

## 0. Что должно быть готово до Meta

1. Проект задеплоен и доступен по публичному HTTPS-домену.
   Пример:

   ```text
   https://crm.example.com
   ```

2. В production env указаны доменные настройки:

   ```env
   APP_DOMAIN=https://crm.example.com
   DJANGO_ALLOWED_HOSTS=crm.example.com,www.crm.example.com,backend
   CORS_ALLOWED_ORIGINS=https://crm.example.com,https://www.crm.example.com
   DJANGO_DEBUG=False
   ENVIRONMENT=production
   ENABLE_PRODUCTION_SECURITY=True
   ```

3. Миграции применены:

   ```bash
   python manage.py migrate
   ```

4. В CRM можно войти под пользователем нужной организации.

5. В CRM открыть:

   ```text
   Settings -> Integrations -> Instagram
   ```

   Там должны быть поля:

   - `App ID`
   - `App Secret`
   - `Verify Token для вебхука`
   - `Callback URL вебхука`
   - `OAuth Redirect URI`
   - кнопка `Сохранить данные Meta App`
   - кнопка `Подключить Instagram`

## 1. Подготовить Instagram аккаунт

1. Создай новый Instagram аккаунт или войди в тестовый аккаунт.

2. Открой Instagram mobile app.

3. Перейди:

   ```text
   Profile -> Menu -> Account type and tools
   ```

   В некоторых аккаунтах путь может называться:

   ```text
   Profile -> Menu -> For professionals -> Business tools and controls
   ```

4. Нажми:

   ```text
   Switch to professional account
   ```

5. Выбери тип:

   ```text
   Business
   ```

   `Creator` тоже поддерживается Meta, но для CRM и отеля лучше `Business`.

6. Выбери категорию бизнеса.
   Например:

   ```text
   Hotel
   Travel & tourism
   Local business
   ```

7. Заверши настройку professional account.

8. Проверь, что в профиле появился:

   ```text
   Professional dashboard
   ```

Если аккаунт остался personal, Instagram DM через API работать не будет.

## 2. Создать или подготовить Facebook Page

1. Открой Facebook под тем же человеком, который будет админом Meta Business.

2. Создай страницу:

   ```text
   facebook.com/pages/create
   ```

   Или через Meta Business Suite:

   ```text
   business.facebook.com -> Settings -> Accounts -> Pages -> Add
   ```

3. Заполни минимум:

   - Page name
   - Category
   - Contact info

4. Убедись, что у твоего Facebook пользователя есть полный доступ к Page:

   ```text
   Meta Business Suite -> Settings -> Accounts -> Pages -> [твоя Page] -> People
   ```

   Нужен доступ уровня admin/full control.

## 3. Подключить Instagram к Странице Facebook / бизнес-портфелю

Этот раздел написан под русский интерфейс Meta Business Suite.

Судя по твоему экрану, ты уже находишься здесь:

```text
https://business.facebook.com
```

И выбран актив `Nomad Camp`. На верхней карточке уже видны две ссылки:

```text
Редактировать Страницу Facebook
Редактировать профиль Instagram
```

Это хороший знак: Meta Business Suite уже видит и Facebook Page, и Instagram профиль в одном рабочем пространстве. Теперь нужно проверить, что связка оформлена правильно.

### 3.1. Быстрая проверка с текущего экрана

1. На главной странице Meta Business Suite проверь левый верхний блок выбора актива.

   У тебя он выглядит примерно так:

   ```text
   Nomad Camp, ...
   ```

2. Убедись, что на центральной карточке страницы есть обе ссылки:

   ```text
   Редактировать Страницу Facebook
   Редактировать профиль Instagram
   ```

3. Если обе ссылки есть, Instagram уже подключен к Meta Business Suite.

4. Нажми:

   ```text
   Входящие
   ```

   в левом меню.

5. Если Meta предложит включить единый inbox для Facebook и Instagram, согласись.

6. Проверь, что в `Входящие` есть вкладка или фильтр Instagram.

Если `Входящие` умеют показывать Instagram, значит связка для сообщений на уровне Business Suite, скорее всего, уже нормальная.

### 3.2. Проверить Page и Instagram через настройки

1. В левом меню нажми:

   ```text
   Настройки
   ```

   На твоём скрине эта кнопка находится почти внизу слева, с иконкой шестерёнки.

2. Если открылось окно настроек Meta Business Suite, найди раздел:

   ```text
   Бизнес-активы
   ```

   или:

   ```text
   Аккаунты
   ```

   Meta иногда показывает разные названия в зависимости от аккаунта.

3. Открой:

   ```text
   Страницы
   ```

4. Проверь, что в списке есть:

   ```text
   Nomad Camp
   ```

5. Нажми на страницу `Nomad Camp`.

6. Проверь, что у твоего пользователя есть полный доступ.

   В русском интерфейсе это может называться:

   ```text
   Полный доступ
   ```

   или:

   ```text
   Управление
   ```

   или:

   ```text
   Доступ администратора
   ```

7. Теперь в том же разделе настроек найди:

   ```text
   Аккаунты Instagram
   ```

8. Открой Instagram аккаунт.

9. Проверь, что там указан твой профессиональный Instagram профиль.

10. Если рядом есть кнопка:

   ```text
   Подключить объекты
   ```

   или:

   ```text
   Назначить объекты
   ```

   или:

   ```text
   Добавить объекты
   ```

   нажми её и назначь Instagram аккаунту страницу:

   ```text
   Nomad Camp
   ```

### 3.3. Если в настройках нет Instagram аккаунта

1. В левом меню Meta Business Suite нажми:

   ```text
   Настройки
   ```

2. Открой:

   ```text
   Аккаунты -> Аккаунты Instagram
   ```

3. Нажми:

   ```text
   Добавить
   ```

4. Выбери:

   ```text
   Подключить аккаунт Instagram
   ```

5. Войди в Instagram аккаунт.

6. Разреши доступ Meta Business Suite.

7. После подключения вернись:

   ```text
   Аккаунты -> Страницы
   ```

8. Убедись, что страница `Nomad Camp` тоже добавлена.

9. Если страницы нет, нажми:

   ```text
   Добавить
   ```

   и выбери один из вариантов:

   ```text
   Добавить Страницу
   ```

   или:

   ```text
   Создать новую Страницу
   ```

### 3.4. Что должно получиться в конце этого шага

К концу шага 3 должно быть так:

- В Meta Business Suite выбран бизнес/актив `Nomad Camp`.
- В `Настройки -> Аккаунты -> Страницы` есть Facebook Page `Nomad Camp`.
- В `Настройки -> Аккаунты -> Аккаунты Instagram` есть профессиональный Instagram аккаунт.
- Instagram аккаунт связан со страницей `Nomad Camp`.
- На главной Meta Business Suite видны ссылки:

  ```text
  Редактировать Страницу Facebook
  Редактировать профиль Instagram
  ```

- В `Входящие` можно работать с сообщениями Instagram.

Без связки `Instagram профессиональный аккаунт -> Страница Facebook` Meta не будет отдавать DM через API.

## 4. Создать Meta Developer App

1. Открой:

   ```text
   https://developers.facebook.com/apps
   ```

2. Ты должен увидеть экран:

   ```text
   Приложения
   Приложений нет
   Создайте свое первое приложение.
   ```

3. Нажми зеленую кнопку:

   ```text
   Создать приложение
   ```

   Она может быть справа сверху или по центру карточки.

4. Если Meta спросит, что приложение должно делать, выбери use case:

   ```text
   Управление сообщениями и контентом в Instagram
   ```

   В английском интерфейсе это называется:

   ```text
   Manage messaging and content on Instagram
   ```

5. Если такого пункта нет, выбери:

   ```text
   Другое
   ```

   Потом тип приложения:

   ```text
   Бизнес
   ```

   В английском интерфейсе:

   ```text
   Other -> Business
   ```

6. Заполни поля:

   - `Название приложения`: например `Axon CRM Instagram`
   - `Контактный email приложения`: твой рабочий email
   - `Бизнес-портфолио`: выбери портфолио, где лежат `Nomad Camp` и `@metabekmametov`

   Для твоего текущего теста нужно выбрать бизнес-портфолио:

   ```text
   metabekmametov
   ```

   Не выбирай вариант "не подключать бизнес-портфолио", если Meta дает выбор.

7. Нажимай:

   ```text
   Далее
   ```

   пока не дойдешь до финального экрана.

8. На последнем экране нажми:

   ```text
   Создать приложение
   ```

9. Если Meta попросит пароль Facebook или 2FA, подтверди.

10. После создания ты должен попасть в `Панель приложения` / `App Dashboard`.

## 5. Заполнить Basic Settings приложения

1. В Meta App Dashboard открой:

   ```text
   Настройки приложения -> Основное
   ```

   В английском интерфейсе:

   ```text
   App settings -> Basic
   ```

2. Заполни обязательные поля:

   - `Домены приложения`: домен CRM без `https://`
   - `URL политики конфиденциальности`: публичная ссылка на privacy policy
   - `Удаление данных пользователя`: URL или инструкция
   - `Категория`: Business / Utility / Business and Pages, если доступно
   - `Значок приложения`, если Meta требует перед Live/App Review

   Пример для домена:

   ```text
   crm.example.com
   ```

   Если проверяешь через ngrok, домен будет без `https://`:

   ```text
   xxxx.ngrok-free.app
   ```

3. Если внизу есть блок `Добавить платформу`, нажми:

   ```text
   Добавить платформу -> Сайт
   ```

   В поле `URL сайта` вставь публичный адрес CRM:

   ```text
   https://crm.example.com
   ```

   Для ngrok:

   ```text
   https://xxxx.ngrok-free.app
   ```

4. Нажми:

   ```text
   Сохранить изменения
   ```

5. На этой странице пока не копируй `ID приложения` и `Секрет приложения` для Instagram.

   Для нового `Instagram API with Instagram Login` в CRM нужно вставлять именно:

   - `Instagram App ID`
   - `Instagram App Secret`

   Они находятся не в `Настройки приложения -> Основное`, а в разделе:

   ```text
   Instagram -> API setup with Instagram login
   ```

   Если вставить обычный Meta `ID приложения`, Instagram OAuth может вернуть ошибку:

   ```text
   Invalid platform app
   ```

## 6. Настроить Instagram API на текущем экране Meta

После создания приложения Meta может сразу открыть экран Instagram API со списком шагов:

```text
1. Добавьте необходимые разрешения для обмена сообщениями
2. Сгенерируйте маркеры доступа
3. Настройте Webhooks
4. Настройте вход в Instagram от имени компании
5. Пройдите проверку приложения
```

Это правильный экран. Дальше работай именно с этими карточками.

### 6.1. Шаг 1: разрешения

На твоем экране шаг 1 уже отмечен зеленой галочкой. Это нормально.

Meta показывает три разрешения:

```text
instagram_business_basic
instagram_manage_comments
instagram_business_manage_messages
```

Для CRM критичны:

```text
instagram_business_basic
instagram_business_manage_messages
```

`instagram_manage_comments` можно оставить, если Meta добавила его автоматически.

### 6.1.1. Найти Instagram App ID и Instagram App Secret

На этом же экране Instagram API найди блок с учетными данными приложения.

Обычно он находится выше или ниже карточек настройки и называется примерно так:

```text
API setup with Instagram login
```

или:

```text
Настройка API с входом через Instagram
```

Скопируй именно эти значения:

```text
Instagram App ID
Instagram App Secret
```

В русском интерфейсе они могут быть подписаны как:

```text
ID приложения Instagram
Секрет приложения Instagram
```

Важно: это не то же самое, что общий `ID приложения` из `Настройки приложения -> Основное`.

### 6.2. Шаг 4: URL переадресации для входа Instagram

Если ты нажал:

```text
4. Настройте вход в Instagram от имени компании -> Настроить
```

и открылось окно:

```text
Настройте вход в Instagram от имени компании
URL переадресации
```

сюда вставляется не webhook URL, а OAuth Redirect URI из CRM.

1. В CRM открой:

   ```text
   Settings -> Integrations -> Instagram
   ```

2. Найди поле:

   ```text
   OAuth Redirect URI
   ```

3. Скопируй его целиком.

   Формат должен быть такой:

   ```text
   https://YOUR_PUBLIC_DOMAIN/api/integrations/instagram/callback/
   ```

   Для production:

   ```text
   https://crm.example.com/api/integrations/instagram/callback/
   ```

   Для ngrok:

   ```text
   https://xxxx.ngrok-free.app/api/integrations/instagram/callback/
   ```

4. Вставь этот URL в поле Meta:

   ```text
   URL переадресации
   ```

5. Нажми:

   ```text
   Сохранить
   ```

Важно: URL должен совпадать символ в символ. Особенно проверь:

- `https://`, не `http://`
- правильный домен
- путь `/api/integrations/instagram/callback/`
- последний `/`

Не вставляй сюда:

```text
/api/integrations/instagram/webhook/
```

Webhook URL нужен в следующем шаге.

### 6.3. Шаг 3: Webhooks на этой же странице

В карточке:

```text
3. Настройте Webhooks
```

заполни два поля.

В поле:

```text
URL обратного вызова
```

вставь webhook URL из CRM:

```text
https://YOUR_PUBLIC_DOMAIN/api/integrations/instagram/webhook/
```

В поле:

```text
Подтверждение маркера
```

вставь тот же `Verify Token для вебхука`, который сохранен в CRM.

Пример token:

```text
axon_instagram_verify_2026_random_text
```

Переключатель:

```text
Прикрепите сертификат клиента к запросам Webhooks
```

оставь выключенным.

После заполнения нажми:

```text
Подтвердить и сохранить
```

Если кнопка не активна, проверь, что заполнены оба поля.

Предупреждение Meta:

```text
Для получения уведомлений Webhooks у приложения должен быть статус "Опубликовано".
```

Это значит: сохранить webhook можно сейчас, но для реальной доставки входящих DM приложение в итоге нужно перевести в Live/Published и пройти проверку приложения.

### 6.4. Шаг 2: маркеры доступа

Кнопка:

```text
Добавить аккаунт
```

нужна для тестовых токенов в интерфейсе Meta. Для CRM основное подключение будет через кнопку:

```text
Подключить Instagram
```

в самой CRM.

Если Meta не дает двигаться дальше без шага 2, нажми `Добавить аккаунт`, выбери свой Instagram `@metabekmametov` и подтверди тестовый доступ.

Если Meta пишет, что сначала нужно назначить роль тестировщика Instagram:

1. Открой в Meta App Dashboard:

   ```text
   Роли
   ```

2. Добавь свой Instagram/Facebook аккаунт как tester/developer для этого приложения.

3. Вернись в Instagram API setup и снова нажми:

   ```text
   Добавить аккаунт
   ```

## 7. Сохранить App credentials в CRM

1. В CRM открой:

   ```text
   Settings -> Integrations -> Instagram
   ```

2. Вставь:

   - `Instagram App ID` / `ID приложения Instagram`
   - `Instagram App Secret` / `Секрет приложения Instagram`

   Эти значения бери из:

   ```text
   Instagram -> API setup with Instagram login
   ```

   Не бери общий `ID приложения` из:

   ```text
   Настройки приложения -> Основное
   ```

3. В поле `Verify Token для вебхука` придумай случайную строку.
   Например:

   ```text
   axon_instagram_verify_2026_random_text
   ```

   Не используй пробелы.

4. Нажми:

   ```text
   Сохранить данные Meta App
   ```

5. Должен появиться статус:

   ```text
   Готово
   ```

6. После сохранения CRM покажет актуальные URL:

   - `Callback URL вебхука`
   - `OAuth Redirect URI`

## 8. Проверить Instagram Webhook в Meta

В новом интерфейсе Meta отдельного пункта `Webhooks` / `Вебхуки` в левом меню может не быть. Это нормально.

Webhook настраивается прямо на экране Instagram API, в карточке:

```text
3. Настройте Webhooks
```

Если ты уже заполнил там:

- `URL обратного вызова`
- `Подтверждение маркера`

и нажал:

```text
Подтвердить и сохранить
```

то отдельный пункт `Webhooks` искать не нужно.

Для CRM значения должны быть такими:

```text
URL обратного вызова:
https://YOUR_PUBLIC_DOMAIN/api/integrations/instagram/webhook/
```

```text
Подтверждение маркера:
тот же Verify Token, который сохранен в CRM
```

Пример для ngrok:

```text
https://xxxx.ngrok-free.app/api/integrations/instagram/webhook/
```

Если `Подтвердить и сохранить` падает, почти всегда причина одна из этих:

- `APP_DOMAIN` в production env не совпадает с реальным доменом.
- Backend не доступен по HTTPS снаружи.
- В CRM и Meta разные Verify Token.
- В webhook URL нет последнего `/`.
- Домен не добавлен в `DJANGO_ALLOWED_HOSTS`.

## 9. Добавить тестового пользователя в Meta App

Для первого теста можно оставить приложение в Development Mode. Но тогда подключаться сможет только пользователь, добавленный в роли приложения.

1. В Meta App Dashboard открой:

   ```text
   App roles -> Roles
   ```

2. Нажми:

   ```text
   Add people
   ```

3. Добавь Facebook пользователя, который владеет/администрирует:

   - Facebook Page
   - Business Portfolio
   - Instagram professional account

4. Выдай роль:

   ```text
   Developer
   ```

   или:

   ```text
   Tester
   ```

5. Пользователь должен принять приглашение, если Meta его отправила.

Если аккаунт не добавлен в роли приложения, в Development Mode OAuth может закончиться ошибкой вроде `App not active`, `App not set up`, `user is not allowed` или похожей.

## 10. Подключить Instagram в CRM

1. В CRM открой:

   ```text
   Settings -> Integrations -> Instagram
   ```

2. Проверь:

   - статус credentials: `Готово`
   - `OAuth Redirect URI` совпадает с Meta
   - `Callback URL вебхука` совпадает с Meta webhook

3. Нажми:

   ```text
   Подключить Instagram
   ```

4. Откроется popup Instagram/Meta.

5. Войди в тот Instagram professional account, который связан с Facebook Page.

6. Разреши доступ.

7. Popup должен закрыться сам.

8. В CRM должен появиться подключенный аккаунт:

   ```text
   @instagram_username
   ```

9. Если CRM показывает ошибку, сначала смотри текст в карточке Instagram. Мы специально вывели туда последнюю OAuth-ошибку.

## 11. Проверить входящие DM

1. Возьми второй Instagram аккаунт.

2. Напиши DM на подключенный professional Instagram аккаунт.

3. В CRM открой:

   ```text
   Communications
   ```

4. Должен появиться новый диалог/lead с Instagram сообщением.

5. Если сообщение не пришло за 1-2 минуты:

   - Проверь Meta Webhooks -> Instagram -> `messages` подписан.
   - Проверь, что после OAuth CRM смогла вызвать `subscribed_apps`.
   - В CRM нажми `Resubscribe webhook`, если такая кнопка доступна.
   - Проверь backend logs.

## 12. Проверить исходящие DM

1. В CRM открой диалог Instagram.

2. Отправь короткое сообщение.

3. Проверь, что оно пришло в Instagram.

4. Если отправка падает:

   - Проверь, что Instagram token не истек.
   - Проверь, что подключен именно professional account.
   - Проверь, что app имеет доступ к `instagram_business_manage_messages`.
   - Проверь, что пользователь уже писал в этот Instagram аккаунт. Instagram messaging API обычно работает в рамках начатой пользователем переписки.

## 13. Когда переводить приложение в Live Mode

Для тестов можно использовать Development Mode и App Roles.

Для реальных клиентов нужно:

1. Заполнить `App settings -> Basic`.

2. Подготовить Privacy Policy URL и User Data Deletion.

3. Открыть:

   ```text
   App Review -> Permissions and Features
   ```

4. Запросить advanced access для:

   ```text
   instagram_business_basic
   instagram_business_manage_messages
   ```

5. В описании App Review объяснить:

   - CRM получает Instagram DM от гостей/клиентов.
   - Менеджеры отвечают из CRM.
   - AI может помогать отвечать на входящие сообщения.
   - Доступ нужен только для сообщений подключенного professional account.

6. После approval переключить приложение:

   ```text
   App Mode -> Live
   ```

## 14. Быстрый чеклист перед тестом

- Instagram аккаунт: Business или Creator.
- Instagram связан с Facebook Page.
- Facebook Page и Instagram account находятся в одном Business Portfolio.
- Facebook пользователь добавлен в App Roles, если app в Development Mode.
- В CRM сохранены App ID, App Secret, Verify Token.
- В Meta добавлен `OAuth Redirect URI` из CRM.
- В Meta Webhooks добавлен `Callback URL вебхука` из CRM.
- Webhook field `messages` включен.
- Backend доступен по HTTPS.
- Production `APP_DOMAIN` совпадает с реальным доменом.
- В production env нет обязательной необходимости указывать `INSTAGRAM_APP_ID`, `INSTAGRAM_APP_SECRET`, `INSTAGRAM_VERIFY_TOKEN`.

## 15. Полезные ссылки

- Meta: Create an Instagram app  
  https://developers.facebook.com/docs/instagram-platform/create-an-instagram-app/

- Meta: Instagram API with Instagram Login  
  https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/

- Meta: Business Login for Instagram  
  https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login/

- Meta: Instagram Webhooks  
  https://developers.facebook.com/docs/instagram-platform/webhooks/

- Meta: Instagram Messaging API  
  https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api/

- Meta: Instagram App Review  
  https://developers.facebook.com/docs/instagram-platform/app-review/

- Instagram Help: Professional account setup  
  https://help.instagram.com/502981923235522/

- Meta Business Help: Connect Instagram professional account to a Facebook Page  
  https://www.facebook.com/business/help/connect-instagram-to-page
