# Conversation Flows

## Flow: Test Reset Flow
*temp*

### Global Flow Prompt
```text

```

## Flow Cards (States)

### Card 1: Welcome & Greeting (Type: `entry`)

#### Message Template / Rules:
```text
Читай guest_language из Shared Context.
Если booking_step уже заполнен — не приветствуй снова, продолжай с нужного шага.
Если consultant_recommendation заполнен — используй как выбор гостя.

ПЕРЕД ОТПРАВКОЙ — прочитай первое сообщение гостя и выпиши про себя:
— Известны ли даты? (заезд и выезд)
— Известно ли количество гостей?

Считывай естественную речь:
«for 2 guests», «на двоих», «for two», «нас двое» = количество = 2, известно
«for 3», «нас трое», «троих» = количество = 3, известно
«с 22 по 25», «with 22 to 25 march» = даты известны
«на пятницу» = только заезд, выезд неизвестен

ПРАВИЛО ПРИВЕТСТВИЯ:
Первую часть отправляй ВСЕГДА — без имени, без исключений.
Затем добавляй ТОЛЬКО те вопросы на которые гость ещё НЕ ответил.

RU (первая часть — обязательна):
«Здравствуйте!
Вы обратились в отель Nomad Camp на южном берегу Иссык-Куля 🌊
С радостью подскажу по размещению.»

EN (первая часть — обязательна):
«Hello!
You've reached Nomad Camp on the southern shore of Lake Issyk-Kul 🌊
I'd be happy to help with your stay.»

KY (первая часть — обязательна):
«Саламатсызбы!
Nomad Camp мейманканасына кош келиңиз 🌊
Жайгашуу боюнча жардам берүүгө даярмын.»

ЗАТЕМ — добавляй только недостающее:

Если даты НЕ известны → добавь:
RU: «📅 На какие даты вы планируете отдых?»
EN: «📅 What dates are you planning?»
KY: «📅 Кайсы күндөргө пландап жатасыз?»

Если количество НЕ известно → добавь:
RU: «👥 Сколько человек будет?»
EN: «👥 How many guests will there be?»
KY: «👥 Канча киши болосуз?»

Если и даты и количество известны — не задавай вопросов, сразу переходи к Card 2.

ПРИМЕРЫ:

Гость: «Здравствуйте» / «Hello» / «Саламатсызбы»
→ Первая часть + оба вопроса

Гость: «Есть номер на двоих?» / «Room for two?» / «I need a room for 2 guests»
→ Первая часть + только вопрос про даты
   ❌ НЕ спрашивать количество — уже известно

Гость: «Need a room, 2 guests, March 22–25»
→ Первая часть без вопросов → сразу Card 2

Гость: «Нужен номер на троих с 22 по 25»
→ Первая часть без вопросов → сразу Card 2

Гость: «На пятницу, нас двое»
→ Первая часть + только вопрос про дату выезда
   ❌ НЕ спрашивать количество — уже известно

ЗАПРЕЩЕНО:
— Начинать с имени гостя
— Пропускать первую часть приветствия
— Задавать вопрос на который гость уже ответил в первом сообщении
— Отправлять оба вопроса если один уже известен
```

### Card 11: Escalate to Staff (Type: `escalation`)

#### Message Template / Rules:
```text
Читай guest_language из Shared Context.

[Booking Agent вызывает transfer_to_manager с нужным reason и всеми известными данными]

RU: «Передала менеджеру — он свяжется с вами в ближайшее время 🙏»
EN: «Passed to our manager — they'll be in touch shortly 🙏»
KY: «Менеджерге өткөрдүм — жакында байланышат 🙏»
```

### Card 12: Room Selection (Type: `normal`)

#### Message Template / Rules:
```text
Читай guest_language из Shared Context. Отвечай ТОЛЬКО на языке гостя.
Если consultant_recommendation заполнен — используй как выбор, переходи к Card 3.

[Booking Agent вызывает get_room_options или get_family_room]
[Показывает варианты из ответа инструмента — никогда из памяти]

RU формат:
«1. [description] — [standard_price_per_night] сом/ночь
 2. [description] — [standard_price_per_night] сом/ночь
Какой вариант вам ближе? 😊»

EN формат:
«1. [description] — [standard_price_per_night] som/night
 2. [description] — [standard_price_per_night] som/night
Which option works best for you? 😊»

is_multi_room: true →
RU: «(два номера — постараемся разместить рядом)»
EN: «(two rooms — we'll place them next to each other)»
```

### Card 13: Meal Plan Selection (Type: `normal`)

#### Message Template / Rules:
```text
Читай guest_language из Shared Context. Отвечай ТОЛЬКО на языке гостя.
Если consultant_recommendation заполнен на этом шаге — используй как выбор, переходи к Card 4.

[Booking Agent читает meal_plans из ответа get_room_options — не вызывает повторно]
[per_night = полная цена, не доплата. Всегда больше standard_price_per_night]

RU:
«Хотите добавить питание?
— [label] — [per_night] сом/ночь
— [label] — [per_night] сом/ночь
— [label] — [per_night] сом/ночь
Что предпочитаете?»

EN:
«Would you like to add a meal plan?
— [label] — [per_night] som/night
— [label] — [per_night] som/night
— [label] — [per_night] som/night
What works best for you?»

Время питания: завтрак 8:00–10:00 / обед 12:00–14:00 / ужин 18:00–20:00
Меню на месте — на ресепшне подскажут.
```

### Card 14: Alternative Dates / Friendly Close (Type: `normal`)

#### Message Template / Rules:
```text
Читай guest_language из Shared Context. Отвечай ТОЛЬКО на языке гостя.

RU:
«Понимаю! Могу предложить ближайшие свободные даты —
или подберём под ваш удобный период.
Какие даты рассматриваете? 😊»

EN:
«Of course! I can suggest the nearest available dates —
or we can work around your schedule.
What dates work for you? 😊»

KY:
«Түшүндүм! Жакынкы бош күндөрдү сунуштай алам —
же сизге ыңгайлуу убакытты табабыз.
Кайсы күндөр ылайыктуу? 😊»

Если гость называет новые даты →
Booking Agent вызывает get_room_options заново → возврат на Card 2.

Если не заинтересован →
RU: «Без проблем! Когда будете готовы — пишите 🌿
Nomad Camp всегда рад вас принять 🌊»
EN: «No problem at all! Reach out whenever you're ready 🌿
Nomad Camp will be here for you 🌊»
KY: «Эч нерсе эмес! Даяр болгондо жазыңыз 🌿
Nomad Camp сизди күтөт 🌊»
```

### Card 15: Collect Contacts (Type: `normal`)

#### Message Template / Rules:
```text
Читай guest_language из Shared Context. Отвечай ТОЛЬКО на языке гостя.

RU:
«Отлично! Для оформления заявки осталось уточнить:
— Ваше полное имя (ФИО)
[Telegram/Instagram: — Номер телефона]
— Email»

EN:
«Almost there! Just need a few details to complete your request:
— Your full name
[Telegram/Instagram: — Phone number]
— Email»

KY:
«Жакшы! Арызды толтуруу үчүн уточнить кылуу керек:
— Толук атыңыз
[Telegram/Instagram: — Телефон номериңиз]
— Email»

WhatsApp: телефон известен — спрашивай только имя и email.
Если имя уже известно из диалога — не спрашивай снова.
```

### Card 17: Booking Confirmation (Type: `normal`)

#### Message Template / Rules:
```text
Читай guest_language из Shared Context. Отвечай ТОЛЬКО на языке гостя.

[Booking Agent вызывает transfer_to_manager(reason="booking_complete") ДО ответа гостю]
[Передаёт: guest_name, guest_phone, guest_email, checkin_date, checkout_date,
 guest_count, room_description, meal_plan, price_per_night, total_price, platform]

RU:
«{contact_person}, всё принято! 🙏
[description номера], {check_in_date}–{check_out_date},
[питание], итого [total] сом.
Менеджер свяжется с вами в ближайшее время
для подтверждения и предоплаты.
Будем рады вас встретить! 🌊»

EN:
«{contact_person}, all set! 🙏
[Room], {check_in_date}–{check_out_date},
[meal plan], total [total] som.
Our manager will reach out shortly to confirm and arrange the deposit.
We can't wait to welcome you! 🌊»

KY:
«{contact_person}, баары кабыл алынды! 🙏
[Номер], {check_in_date}–{check_out_date},
[тамак], жалпы [total] сом.
Менеджер жакында байланышат.
Сизди кутуп калабыз! 🌊»
```

### Card 18: Temp Card (Type: `normal`)

#### Message Template / Rules:
```text
hi
```

## State Transitions (Connections)

### Connection 9: Эскалация к менеджеру
- **From:** Card 1 (Welcome & Greeting)
- **To:** Card 11 (Escalate to Staff)
- **Keywords:** `корпоратив, юрлицо, сборы, тимбилдинг, конференция, банкет, свадьба, мероприятие, тренер, команда, кэмп, спортивный лагерь, группа, организация, компания, счёт, договор, ивент, event, тренинг, семинар, форум, выездной, корпоративный, спортивный сбор, юридическое лицо, выставить счёт, заключить договор, от организации, от компании, для сотрудников, для команды, массовый заезд, большая группа, много людей, 10 человек, 11 человек, 12 человек, 15 человек, 20 человек, 30 человек, 50 человек, camp, training camp, corporate, conference, teambuilding, team building, event, group booking, sports team, coach, trainer`

### Connection 10: Room Selection
- **From:** Card 1 (Welcome & Greeting)
- **To:** Card 12 (Room Selection)
- **Keywords:** `да, есть, хочу, нужен номер, ищу номер, хотим, планируем, интересует, забронировать, бронь, заселиться, приехать, отдохнуть, остановиться, номер, комната, двухместный, одноместный, стандарт, комфорт, семейный, на двоих, на троих, на четверых, нас двое, нас трое, нас четверо, один человек, два человека, три человека, четыре человека, с девушкой, с женой, с мужем, с другом, с семьёй, с детьми, с ребёнком, январь, февраль, март, апрель, май, июнь, июль, август, сентябрь, октябрь, ноябрь, декабрь, выходные, на неделю, на три дня, на два дня, на ночь, заезд, выезд, с какого, по какое, yes, interested, confirm, book, room, need a room, two people, three people, family, couple, dates, check in, check out, available, availability, looking for, planning`

### Connection 11: Meal Plan Selection
- **From:** Card 12 (Room Selection)
- **To:** Card 13 (Meal Plan Selection)
- **Keywords:** `первый, второй, первый вариант, второй вариант, этот, подходит, окей, ок, беру, берём, хочу этот, выбираю, подойдёт, устраивает, давайте этот, согласен, согласна, да, хорошо, отлично, норм, нормально, стандарт, комфорт, одноместный, двухместный, семейный, номер подходит, устраивает номер, этот номер, вариант 1, вариант 2, 1й, 2й, первый подходит, второй подходит, 1, 2, yes, ok, okay, good, this one, first, second, first option, second option, suits me, works for me, I'll take it, sounds good, perfect, great, confirmed, this works, option 1, option 2`

### Connection 12: Эскалация к менеджеру
- **From:** Card 12 (Room Selection)
- **To:** Card 11 (Escalate to Staff)
- **Keywords:** `корпоратив, юрлицо, сборы, тимбилдинг, конференция, банкет, свадьба, мероприятие, тренер, команда, кэмп, спортивный лагерь, группа, организация, компания, счёт, договор, ивент, тренинг, семинар, форум, выездной, корпоративный, спортивный сбор, юридическое лицо, выставить счёт, заключить договор, от организации, от компании, для сотрудников, для команды, 10 человек, 11 человек, 12 человек, 15 человек, 20 человек, 25 человек, 30 человек, 50 человек, много людей, большая группа, массовый заезд, жалоба, претензия, недоволен, недовольна, проблема, конфликт, возврат, отмена, отменить, вернуть деньги, не устраивает, плохо, ужасно, обман, обещали, не то, corporate, conference, teambuilding, team building, event, group booking, sports team, coach, trainer, complaint, refund, cancel, problem, issue, too many people`

### Connection 13: Not Interested / Alternative Dates
- **From:** Card 12 (Room Selection)
- **To:** Card 14 (Alternative Dates / Friendly Close)
- **Keywords:** `не подходит, не устраивает, дорого, слишком дорого, нет, не хочу, не буду, другие даты, другое время, перенести, другой период, не те даты, занято, нет мест, нет свободных, дорого для нас, бюджет, не по бюджету, подумаю, не готов, не готова, позже, потом, не сейчас, может позже, ещё думаю, позвоню, напишу позже, не определился, не определилась, пока нет, не факт, не уверен, не уверена, рассматриваем, смотрим варианты, сравниваем, альтернатива, другой отель, есть варианты дешевле, у вас дорого, нет подходящего, не то, другой номер, что-то другое, ничего не подошло, спасибо не надо, откажусь, отказываюсь, no, nope, not interested, too expensive, different dates, other dates, maybe later, not now, still thinking, not sure, considering, comparing, too much, out of budget, not a fit, pass, decline, not for us, let me think, I'll pass, not ready`

### Connection 14: New Dates Proposed
- **From:** Card 14 (Alternative Dates / Friendly Close)
- **To:** Card 12 (Room Selection)
- **Keywords:** `давайте, подойдёт, тогда, другие даты, вот эти даты, как насчёт, а можно, попробуем, рассмотрим, другой период, другое число, перенесём, заезд, выезд, с такого-то, по такое-то, январь, февраль, март, апрель, май, июнь, июль, август, сентябрь, октябрь, ноябрь, декабрь, понедельник, вторник, среда, четверг, пятница, суббота, воскресенье, на следующей неделе, на этой неделе, через неделю, через месяц, в начале, в конце, в середине, числа, число, даты, дата, ближайшие, свободные даты, когда есть, что есть, что свободно, check in, check out, how about, what about, these dates, new dates, different dates, let's try, let's go with, how about this, available, when is available, next week, next month`

### Connection 15: Эскалация из питания
- **From:** Card 13 (Meal Plan Selection)
- **To:** Card 11 (Escalate to Staff)
- **Keywords:** `жалоба, не устраивает, плохо, проблема, верните, возврат, отмена, отменить, корпоратив, юрлицо, счёт, договор, сборы, тренер, команда, группа, 10 человек, 15 человек, 20 человек, много людей, большая группа, не то, не подходит, другое, не знаю, помогите, позвоните, перезвоните, свяжитесь, менеджер, администратор, человек, живой человек, complaint, refund, cancel, corporate, invoice, contract, group, manager, speak to someone, human, real person, not interested, problem, issue`

### Connection 16: Meal Plan Confirmed
- **From:** Card 13 (Meal Plan Selection)
- **To:** Card 15 (Collect Contacts)
- **Keywords:** `первый, второй, третий, первый вариант, второй вариант, третий вариант, завтрак, полупансион, полный пансион, без питания, не надо питания, только проживание, только номер, без еды, с завтраком, с питанием, завтрак устраивает, полупансион подходит, полный пансион беру, да питание, хочу завтрак, хочу полупансион, хочу полный пансион, берём завтрак, берём полупансион, берём полный пансион, подходит, окей, ок, да, хорошо, устраивает, нормально, давайте, согласен, согласна, 1, 2, 3, вариант 1, вариант 2, вариант 3, breakfast, half board, full board, no meals, without meals, room only, just the room, with breakfast, yes meals, I'll take breakfast, I'll take half board, I'll take full board, ok, yes, good, sounds good, confirmed, this one, option 1, option 2, option 3`

### Connection 17: Передумал на этапе контактов
- **From:** Card 15 (Collect Contacts)
- **To:** Card 14 (Alternative Dates / Friendly Close)
- **Keywords:** `подождите, стоп, отменить, не буду, передумал, передумала, подумаю, не готов, не готова, позже, потом, не сейчас, слишком дорого, дорого, пересмотрю, другие варианты, другой отель, не то, не подходит, не устраивает, отложим, может потом, ещё раз подумаю, не уверен, не уверена, отказываюсь, нет, стоп стоп, подождите пожалуйста, hold on, wait, cancel, never mind, changed my mind, not sure, too expensive, let me think, not ready, maybe later, I'll pass, not for now, reconsidering, different option`

### Connection 18: Эскалация из контактов
- **From:** Card 15 (Collect Contacts)
- **To:** Card 11 (Escalate to Staff)
- **Keywords:** `корпоратив, юрлицо, организация, компания, от компании, счёт, договор, тимбилдинг, конференция, банкет, сборы, тренер, команда, группа, много людей, 10 человек, 15 человек, 20 человек, жалоба, проблема, конфликт, возврат, отмена, не устраивает, претензия, хочу вернуть, хочу отменить, не могу приехать, форс-мажор, corporate, invoice, contract, group, refund, cancel, complaint, issue, problem`

### Connection 19: Contacts Provided
- **From:** Card 15 (Collect Contacts)
- **To:** Card 17 (Booking Confirmation)
- **Keywords:** `вот, держите, записывайте, мой номер, мой email, моя почта, пишу, скидываю, отправляю, ФИО, фамилия, имя, отчество, телефон, номер телефона, почта, email, e-mail, электронная почта, gmail, mail, inbox, yandex, bk.ru, hotmail, outlook, @, +996, +7, +998, 0700, 0500, 0550, 0770, 0312, готово, всё, вот данные, вот информация, записал, записала, вот мои данные, заполнил, заполнила, yes, here, here it is, my name, my phone, my email, my contact, sending, there you go, done, all set, here are my details`

### Connection 20: Not Interested in Meal Plans
- **From:** Card 13 (Meal Plan Selection)
- **To:** Card 14 (Alternative Dates / Friendly Close)
- **Keywords:** `не нужно, не надо, без питания, не хочу есть, не буду, откажусь, отказываюсь, только номер, просто номер, без еды, не интересует, не берём, пропустим, пропустить, не требуется, обойдёмся, сами поедим, своя еда, привезём еду, дорого, слишком дорого, не по бюджету, не подходит, другой вариант, подумаю, не готов, не готова, позже, потом, передумал, передумала, не уверен, не уверена, стоп, подождите, отменить, не то, не устраивает, другой отель, пересмотрю, no meals, no food, room only, just the room, skip, no thanks, not interested, without meals, too expensive, changed my mind, never mind, hold on, wait, cancel, not sure, maybe later, I'll pass, not for now, reconsidering, different option, no meal plan, no board`

