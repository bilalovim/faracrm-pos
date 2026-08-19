# Copyright 2025 FARA CRM
# Chat Phone Asterisk module - Asterisk / FreePBX webhook & CDR adapter

from datetime import datetime

from backend.base.crm.chat_phone.strategies.adapter import (
    PhoneMessageAdapter,
    digits_only as _digits,
)


class AsteriskPhoneAdapter(PhoneMessageAdapter):
    """
    Адаптер Asterisk / FreePBX.

    Понимает ДВА формата входящих данных (различаются по структуре):

    1) ARI-событие (живой сигнал, прилетает от Asterisk-agent на webhook):
       {
         "type": "ChannelStateChange" | "ChannelDestroyed" | "ChannelHangupRequest",
         "timestamp": "2024-05-11T16:04:53.044+0300",
         "channel": {
             "id": "1715432693.70626",              # uniqueid канала
             "name": "SIP/9624032060_out-000080ca",
             "state": "Down" | "Ring" | "Up",
             "caller":    {"name": "", "number": "+79614889972"},
             "connected": {"name": "", "number": ""},
             "dialplan":  {"app_name": "AppDial" | "", "exten": "...", ...}
         },
         "application": "AsteriskAgentPython"
       }
       Используется только для «живого» пузыря звонка (event_type=answered).
       Финализация (запись, длительность, disposition) приходит из CDR:
       на hangup стратегия до-запрашивает CDR по uniqueid у агента.

    2) CDR-запись (из истории звонков агента /api/calls/hisroty/):
       {
         "calldate": "2024-05-16T16:29:18",
         "src": "9624032060", "dst": "89624515599",
         "channel": "SIP/307-00008246",
         "dstchannel": "SIP/9624032060_out-00008247",
         "duration": 37, "billsec": 29,
         "disposition": "ANSWERED" | "NO ANSWER" | "BUSY" | "FAILED",
         "uniqueid": "1715866158.71448",
         "linkedid": "1715866158.71448",
         "recordingfile": "out-89624515599-307-...-....mp3",
         "lastapp": "Dial"
       }
       Это источник истины для сохранённого звонка (event_type=ended).
    """

    # ------------------------------------------------------------- shape
    # Выносим маркеры на уровень класса как защищенную константу.
    # Это экономит память и процессорное время.
    _ARI_INDICATORS: frozenset[str] = frozenset(
        {
            "channel",
            "bridge",
            "endpoint",
            "playback",
            "recording",
            "application",
        }
    )

    @property
    def is_ari(self) -> bool:
        """
        ARI-событие гарантированно содержит строковое поле 'type'
        и один из ключевых объектов иерархической структуры ARI JSON.
        """
        raw_type = self.raw.get("type")
        if not isinstance(raw_type, str):
            return False

        # Быстрая проверка: пересекаются ли ключи нашего JSON с маркерами ARI.
        # Метод isdisjoint() в Python работает на C-уровне и оптимизирован по скорости.
        return not self._ARI_INDICATORS.isdisjoint(self.raw)

    @property
    def _channel(self) -> dict:
        return self.raw.get("channel") or {}

    # --------------------------------------------------------- lifecycle
    @property
    def event_type(self) -> str:
        """
        Классифицирует тип события для CRM.
        Разделяет начало/процесс, ответ и реальное завершение звонка.
        """
        if not self.is_ari:
            # Для CDR записей из БД — это всегда историческое (завершенное) событие
            return "ended"

        etype = self.raw.get("type")
        channel = self.raw.get("channel") or {}

        # 1. Определение ответа (answered)
        # Вариант А: Стандартное изменение состояния канала на Up (для любых вызовов)
        if etype == "ChannelStateChange" and channel.get("state") == "Up":
            return "answered"

        # Вариант Б: Специализированное событие Dial из ARI (подстраховка)
        if etype == "Dial":
            dialstatus = self.raw.get("dialstatus") or ""
            if dialstatus.upper() == "ANSWER":
                return "answered"

        # Вариант В: Вход в бридж (гарантия того, что люди начали говорить)
        if etype == "BridgeEnter":
            return "answered"

        # 2. Точное определение НАСТОЯЩЕГО завершения звонка
        if etype == "ChannelDestroyed":
            return "ended"

        # 3. Все остальные события (StasisStart, ChannelLeft, HangupRequest и т.д.)
        return "progress"

    # --------------------------------------------------------- direction
    @property
    def call_direction(self) -> str:
        """
        Направление звонка (ARI и CDR) по НАШИМ номерам.

        Приоритет:
        1. Префикс файла записи: out-… (исходящий) / in-… (входящий).
        2. По кэшу наших номеров (_is_internal):
           - оба наши          → "internal" (клиента НЕТ, звонок сотрудник↔сотрудник);
           - наш → не наш      → "outgoing";
           - не наш → наш      → "incoming";
           - оба чужие (транзит через АТС / мусор) → "incoming".
        """
        # 1. Сначала проверяем запись, как самый приоритетный источник
        recordingfile = (self.raw.get("recordingfile") or "").lower()
        if recordingfile.startswith("out-"):
            return "outgoing"
        if recordingfile.startswith("in-"):
            return "incoming"

        # 2. Переиспользуем наши очищенные и валидированные свойства номеров
        src = self.caller_number
        dst = self.callee_number

        # 3. Определяем направление на основе того, внутренние ли номера
        src_internal = self._is_internal(src)
        dst_internal = self._is_internal(dst)

        if src_internal and dst_internal:
            return "internal"  # оба наши → клиента нет

        if src_internal and not dst_internal:
            return "outgoing"

        # не наш → наш, либо оба чужие (транзит) → входящий
        return "incoming"

    # Множество НАШИХ номеров коннектора (цифры extension/number всех его линий),
    # грузится в cache_numbers. None → не звали → fallback.
    _our_numbers: "set[str] | None" = None

    async def cache_numbers(self, env) -> None:
        """
        Загрузить номера коннектора (модель phone_number) в множество. По нему
        _is_internal = «это наша линия».

        Берём ВСЕ линии, а не только привязанные к сотрудникам: то же правило,
        по которому пайплайн определяет нашу ногу звонка
        (PhoneNumber.find_by_number). Раньше здесь стоял фильтр по user_id —
        от старой архитектуры, где «наш/клиент» решал адаптер; после переезда
        на реестр номеров две трактовки «наш номер» разъезжались на линии без
        сотрудника. Один запрос на звонок.
        """
        rows = await env.models.phone_number.search(
            filter=[("connector_id", "=", self.connector.id)],
            fields=["extension", "number"],
        )
        nums: "set[str]" = set()
        for row in rows:
            for value in (row.extension, row.number):
                digits = _digits(value)
                if digits:
                    nums.add(digits)
        self._our_numbers = nums

    def _is_internal(self, number: str | None) -> bool:
        """
        Внутренний = НАША линия (есть в реестре phone_number коннектора). До
        cache_numbers (номера ещё не загружены) — fallback на длину (≤ 5 цифр).
        """
        digits = _digits(number)
        if not digits:
            return False
        if self._our_numbers is not None:
            return digits in self._our_numbers
        return len(digits) <= 5

    # ------------------------------------------------------------ numbers
    @property
    def _ari_is_dialed_leg(self) -> bool:
        """
        Канал создан Dial'ом — номера в нём ЗЕРКАЛЬНЫ: caller.number это
        вызываемый (равен dialplan.exten), connected.number — инициатор.
        На живых событиях: исходящий 201→8918 (канал транка: caller=8918,
        connected=201), входящий 7918→201 (канал PJSIP/201: caller=201,
        connected=7918). «Сняли трубку» ловится именно на таком канале.
        """
        dialplan = self._channel.get("dialplan") or {}
        return dialplan.get("app_name") == "AppDial"

    @property
    def caller_number(self) -> str:
        """Инициатор звонка (src). Очищает служебный мусор Asterisk."""
        if self.is_ari:
            side = "connected" if self._ari_is_dialed_leg else "caller"
            src = (self._channel.get(side) or {}).get("number") or ""

            # Редкий фолбек: если номер пуст, но есть dialplan context
            if not src:
                dialplan = self._channel.get("dialplan") or {}
                src = dialplan.get("caller_id_num") or ""
        else:
            src = self.raw.get("src") or ""

        # Приводим к строке и убираем пробелы
        src = str(src).strip()

        # Фильтруем текстовую заглушку анонимных звонков
        if src.lower() in ("unknown", "anonymous", "restricted", "hidden"):
            return ""

        return src

    @property
    def callee_number(self) -> str:
        """
        Вызываемый (dst). У ARI «connected» на хэнгапе бывает пуст — тогда берём
        набранный exten диалплана. Спец-значения диалплана (h/s/i/t/unknown) отсекаются.
        """
        if self.is_ari:
            dialplan = self._channel.get("dialplan") or {}
            side = "caller" if self._ari_is_dialed_leg else "connected"
            # Безопасное извлечение с фолбеком на набранный exten
            dst = (
                (self._channel.get(side) or {}).get("number")
                or dialplan.get("exten")
                or ""
            )

            # Очищаем от пробелов и приводим к нижнему регистру для надежной проверки
            dst_clean = dst.strip().lower()

            # Расширенный список системных экстеншенов Asterisk
            invalid_extensions = ("h", "s", "i", "t", "fax", "unknown", "")

            return "" if dst_clean in invalid_extensions else dst.strip()

        # Для не-ARI (например, AMI или CDR)
        return str(self.raw.get("dst") or "").strip()

    @property
    def author_id(self) -> str:
        """
        Автор = нормализованный номер КЛИЕНТА.

        Входящий: клиент = caller (src).
        Исходящий: клиент = callee (dst).
        Нормализация → все звонки одного клиента ложатся в один чат.
        """
        # Используем уже очищенные свойства, чтобы не нормализовать "unknown" или пробелы
        client_phone = (
            self.caller_number
            if self.call_direction == "incoming"
            else self.callee_number
        )
        return self.normalize_phone(client_phone)

    @property
    def internal_number(self) -> str | None:
        """
        Внутренний номер (extension) оператора.
        Работает универсально для ARI, AMI и CDR.
        """
        # Берем уже полностью очищенные и валидированные номера
        caller = self.caller_number
        callee = self.callee_number

        # Исходящий: оператор звонит клиенту. Оператор = caller (src)
        if self.call_direction == "outgoing" and self._is_internal(caller):
            return _digits(caller) or None

        # Входящий: клиент звонит в компанию. Оператор = callee (dst)
        if self.call_direction == "incoming" and self._is_internal(callee):
            return _digits(callee) or None

        return None

    # ---------------------------------------------------------------- ids
    @property
    def message_id(self) -> str:
        """
        Канонический id звонка (для связи событий одного звонка).

        CDR: linkedid (переживает переводы), fallback uniqueid.
        ARI: id канала. Для мерджа ARI-пузыря с CDR стратегия ищет
             существующее сообщение и по uniqueid тоже.
        """
        if self.is_ari:
            return str(self._channel.get("id", "") or "")
        return str(self.raw.get("linkedid") or self.raw.get("uniqueid") or "")

    @property
    def chat_id(self) -> str:
        """Чат = номер клиента (все звонки клиента → один чат)."""
        return self.author_id

    @property
    def author_name(self) -> str | None:
        """Имя автора — номер клиента (реальное имя определит Contact)."""
        return self.author_id or None

    # -------------------------------------------------------- disposition
    @property
    def disposition(self) -> str:
        """
        Результат звонка (исход) для CRM.
        Универсально обрабатывает исторический CDR и живые события ARI.
        """
        # 1. Логика для живых событий Asterisk REST Interface (ARI)
        if self.is_ari:
            # Если звонок еще идет, его исход пока не ясен — он в процессе
            if self.event_type != "ended":
                return "no_answer"  # или "progress", в зависимости от логики вашей CRM

            # Если звонок завершился, смотрим на статус диала (если он был в событии)
            # Примечание: Asterisk возвращает DIALSTATUS в событии Dial
            dialstatus = (self.raw.get("dialstatus") or "").upper()

            # Также можно проверить стандартные коды завершения Asterisk Cause Codes, если они есть в JSON
            # (например, в объекте channel.get("hangupcause"))
            hangup_cause = int(
                (self.raw.get("channel") or {}).get("hangupcause") or 0
            )

            # Маппинг живых статусов ARI
            if (
                dialstatus == "ANSWER" or hangup_cause == 16
            ):  # 16 = Normal clearing (разговор состоялся)
                return "answered"
            if dialstatus == "BUSY" or hangup_cause == 17:  # 17 = User busy
                return "busy"
            if (
                dialstatus in ("NOANSWER", "NO ANSWER") or hangup_cause == 19
            ):  # 19 = No answer from user
                return "no_answer"
            if dialstatus == "CANCEL":
                return "cancelled"

            # Если точный статус не поймали, но мы знаем, что был факт ответа ранее:
            # (Если в вашей системе сохраняется промежуточный стейт, лучше проверить его,
            # иначе для сброшенных до ответа звонков возвращаем дефолт)
            return "no_answer"

        # 2. Логика для исторических записей из БД (CDR / AMI)
        status = (self.raw.get("disposition") or "").upper().strip()
        mapping = {
            "ANSWERED": "answered",
            "NO ANSWER": "no_answer",
            "NOANSWER": "no_answer",
            "BUSY": "busy",
            "FAILED": "failed",
            "CANCEL": "cancelled",
            "CONGESTION": "failed",
            "CHANUNAVAIL": "failed",
        }
        return mapping.get(status, "failed")

    # ------------------------------------------------------------- timing
    @property
    def _start_ts(self) -> int | None:
        raw_start = self.raw.get("calldate") or self.raw.get("start")
        if not raw_start:
            return None
        if isinstance(raw_start, (int, float)):
            return int(raw_start)
        # JSON от агента: обычно "2024-05-16T16:29:18", но возможны пробел вместо
        # T, миллисекунды, таймзона. fromisoformat (py3.11+) съедает все эти
        # варианты; strptime — запасной.
        if isinstance(raw_start, str):
            iso = raw_start.strip().replace(" ", "T")
            try:
                return int(datetime.fromisoformat(iso).timestamp())
            except (ValueError, TypeError):
                pass
            try:
                return int(
                    datetime.strptime(
                        iso[:19], "%Y-%m-%dT%H:%M:%S"
                    ).timestamp()
                )
            except (ValueError, TypeError):
                return None
        return None

    @property
    def call_duration(self) -> int | None:
        value = self.raw.get("duration")
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @property
    def talk_duration(self) -> int | None:
        value = self.raw.get("billsec")
        if value is None:
            return None
        try:
            return int(value)
        except (ValueError, TypeError):
            return None

    @property
    def call_answer_timestamp(self) -> int | None:
        """Время ответа = старт + (duration - billsec)."""
        start = self._start_ts
        duration = self.call_duration
        billsec = self.talk_duration
        if start is not None and duration is not None and billsec:
            return start + max(0, duration - billsec)
        return None

    @property
    def call_end_timestamp(self) -> int | None:
        start = self._start_ts
        duration = self.call_duration
        if start is not None and duration is not None:
            return start + duration
        return None

    @property
    def created_at(self) -> int:
        return self._start_ts or 0

    # ---------------------------------------------------------- recording
    @property
    def recording_filename(self) -> str | None:
        """Имя файла записи для запроса к агенту (/api/call/recording/)."""
        return self.raw.get("recordingfile") or None

    @property
    def call_record_url(self) -> str | None:
        """
        Маркер наличия записи (триггер для базового _process_call_record).

        Для Asterisk это НЕ прямой URL — запись тянется через API агента
        по filename (см. AsteriskPhoneStrategy._download_call_record).
        Возвращаем имя файла как признак; реальный запрос строит стратегия.
        """
        if not self.is_ari and self.talk_duration and self.recording_filename:
            return self.recording_filename
        return None

    # --------------------------------------------------------------- skip
    @property
    def should_skip(self) -> bool:
        if self.is_ari:
            # ARI фильтруется в стратегии (_handle_ari_event)
            return False
        # CDR без id или без номеров — мусор
        if not (self.raw.get("linkedid") or self.raw.get("uniqueid")):
            return True
        if not self.raw.get("src") or not self.raw.get("dst"):
            return True
        return False
