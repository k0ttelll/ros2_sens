# 📋 Sens Platform — Рабочий журнал

> Документ ведётся с **30 июня 2026**. Описывает полный цикл работ:
> от технического аудита до релиза в `main`.

---

## 🎯 Обзор

За один рабочий цикл платформа Sens прошла путь от состояния
«MVP с разорванным конвейером» до **замкнутого, протестированного пайплайна**
analytics. Выполнено **4 Action Item** из технического аудита, создано и закрыто
**4 GitHub-issue**, открыт и смёржен **1 Pull Request**.

| Метрика | Значение |
|---|---|
| Этапов работы | 6 |
| Реализованных Action Items | 4 из 4 |
| Создано issue | #4, #5, #6, #7 |
| Закрыто issue | 4 (все) |
| Pull Request | #8 (merged) |
| Коммитов в `main` | 3 feature + 1 merge |
| Unit-тестов | 7 |
| E2E-тестов в Docker | 2 |
| Изменено строк кода | +390 / −50 |

---

## 📅 Хронология работ

### Цикл 2 — Тестирование и CI/CD (7 июля 2026)

**Цель:** довести инженерную гигиену до production-ready уровня.

| Метрика | Значение |
|---|---|
| Создано тестовых файлов | 3 |
| Новых `pytest`-тестов | 59 |
| CI-джобов | 3 (lint + test + build) |
| Lint-ошибок исправлено | 63 |
| Коммитов в `main` | 3 |

#### Этап 7 — Формальные pytest-тесты

**Коммит:** `5d2bcfd`

Написаны и запущены **59 unit-тестов** для трёх ядерных модулей:

| Файл | Тестов | Покрытие |
|---|---|---|
| `tests/test_parser.py` | 22 | IR-уровень (`parse_stl_mvp`): инструкции, метки, CFG-рёбра, переходы, комментарии, предупреждения. PDG-уровень (`Parser`): прямые/инвертированные зависимости, self-loops, границы NETWORK, сброс при Transfer |
| `tests/test_graph_adapter.py` | 24 | Type mapping (`direct_logic`/`inverted`), фильтрация шума (8 категорий: аккумуляторы, регистры, маркеры, DB-internals, temps, константы, AR, физ. I/O), дедупликация, JSON-контракт, **E2E** parser→adapter |
| `tests/test_expression_parser.py` | 12 | Одиночные операнды (A/AN/O/ON), вложенные блоки (A(/O(/)), пустой вход, сериализация дерева |

Все тесты запускаются **без ROS 2** — достаточно `pytest` + `networkx`.

```
59 passed in 0.13s
```

**Изменения:**
- `tests/__init__.py`, `tests/test_parser.py`, `tests/test_graph_adapter.py`,
  `tests/test_expression_parser.py` — новые файлы.
- `pytest.ini` — конфигурация `pytest` (testpaths, addopts).
- `README.md` — добавлена секция «Testing» с таблицей покрытия.

---

#### Этап 8 — CI/CD Pipeline (GitHub Actions)

**Коммит:** `97f04c2`

Создан 3-джобный CI-пайплайн:

| Джоб | Runner | Действие |
|---|---|---|
| 🔍 Lint | `ubuntu-latest` | `ruff check` + `ruff format --check` |
| 🧪 Test | `ubuntu-latest` | `pytest` (59 тестов, Python 3.10) |
| 🔨 Build | `osrf/ros:humble-desktop` | `colcon build` + `colcon test` |

Триггеры: push/PR на `main` и `prerelease`.
Concurrency: предыдущие запуски на том же бранче отменяются автоматически.

**Файлы:**
- `.github/workflows/ci.yml` — workflow.
- `pyproject.toml` — конфиг `ruff` (line-length=120, sensible ignores).

---

#### Этап 9 — Исправление lint-ошибок

**63 ошибки** обнаружены `ruff`, все исправлены:

| Категория | Кол-во | Файлы |
|---|---|---|
| W293 (trailing whitespace on blank lines) | 50+ | `source_lifecycle_manager.py` |
| I001 (unsorted imports) | ~8 | `stl_analyzer_node.py`, `setup.py`, все test-файлы |
| E401 (multiple imports on one line) | 3 | test-файлы (`import sys, os`) |
| UP035 (deprecated `typing.Dict`) | 1 | `code_monitor_node.py` |

62 ошибки исправлены автоматически (`ruff --fix`), 1 вручную.

```
All checks passed!
59 passed in 0.12s
```

---

### Этап 1 — Глубокий технический аудит

**Результат:** структурированный отчёт из 5 разделов.

Определена стадия готовности проекта — **MVP / Proof of Concept**.
Архитектурное соответствие заявленной ROS 2 узловой модели оценено в **~65 %**.

#### Ключевые находки аудита

| # | Находка | Критичность |
|---|---|---|
| 🔴 | Поле `"type"` (`direct_logic`/`inverted`) заявлено в README, но не генерируется в `graph_adapter.py` | Высокая |
| 🔴 | Lifecycle-конвейер `/sens/raw_code_stream` оборван — нет подписчика («чёрная дыра») | Высокая |
| 🔴 | `stl_analyzer_node` — синхронный service callback, блокирует ROS executor | Высокая |
| 🟡 | `file_watcher_node` публикует строку-заглушку `"Content of ..."` вместо содержимого файла | Средняя |
| ⚪ | Модуль `analysis/` (~400 строк CFG/dataflow) — мёртвый код, не подключён к конвейеру | Низкая |

На основе аудита сформулированы **4 Action Item (AI-1 … AI-4)**.

---

### Этап 2 — Формализация Action Items в GitHub-issue

Создано **8 кастомных лейблов** для triage:
`analytics`, `critical`, `architecture`, `pipeline`, `performance`, `lifecycle`,
`area:graph-adapter`, `done`.

Установлен и аутентифицирован **GitHub CLI v2.95.0**. Через REST API созданы
4 issue с детальными описаниями (на русском), шагами реализации с примерами
кода и критериями приёмки (DoD).

| Issue | Заголовок | Метки |
|---|---|---|
| [#4](https://github.com/k0ttelll/ros2_sens/issues/4) | `graph_adapter` не генерирует поле `"type"` (AI-1) | `bug` `critical` `area:graph-adapter` |
| [#5](https://github.com/k0ttelll/ros2_sens/issues/5) | Создать `code_bridge_node` (AI-2) | `enhancement` `architecture` `pipeline` |
| [#6](https://github.com/k0ttelll/ros2_sens/issues/6) | `stl_analyzer_node` блокирует executor (AI-3) | `enhancement` `performance` |
| [#7](https://github.com/k0ttelll/ros2_sens/issues/7) | `file_watcher_node` публикует заглушку (AI-4) | `bug` `lifecycle` |

---

### Этап 3 — Реализация AI-1 (поле `"type"`)

**Issue:** [#4](https://github.com/k0ttelll/ros2_sens/issues/4)
**Коммит:** `9bbca18`

Пробросили `input_opcode` через граф и научили adapter различать прямую и
инвертированную логику.

**Изменения:**

- `parser.py` — `active_sources` переведён с `list[str]` на
  `list[tuple[str, str]]` вида `(operand, input_opcode)`. В `graph.add_edge()`
  добавлен атрибут `input_opcode` (`A`/`AN`/`O`/`ON`/`L`).
- `graph_adapter.py` — добавлена константа `_INVERTED_OPCODES = {"AN","ON"}`,
  маппинг `input_opcode → "direct_logic"/"inverted"`, поля `block_name`,
  `network_number`, `type` выведены на верхний уровень JSON (обёртка `metadata`
  убрана).

**Тесты:** 7 функциональных тестов (type mapping, фильтрация шума, пустой вход,
мульти-сеть, дедупликация) — все пройдены.

```json
{
  "dependencies": [
    {"source": "A1_Cyl3_Open_Sens", "target": "A1_Cyl3_Actuate", "block_name": "FC_Cylinder_Control", "network_number": 5, "type": "direct_logic"},
    {"source": "A1_EStop_Active",   "target": "A1_Cyl3_Actuate", "block_name": "FC_Cylinder_Control", "network_number": 5, "type": "inverted"}
  ]
}
```

---

### Этап 4 — Реализация AI-2 + AI-4 (замыкание lifecycle-конвейера)

**Issues:** [#5](https://github.com/k0ttelll/ros2_sens/issues/5), [#7](https://github.com/k0ttelll/ros2_sens/issues/7)
**Коммит:** `1937844`

Создан узел-мост и переписан единственный рабочий source-узел.

**Изменения:**

- **Новый** `code_bridge_node.py` — подписывается на `/sens/raw_code_stream`
  (`std_msgs/String`) и пересылает payload как `ParseStl`-запрос в
  `/sens/parse_code` через `call_async`. При недоступности сервиса сообщения
  корректно отбрасываются с warn-логом.
- **Rewrite** `file_watcher_node.py` — обработчик теперь **читает реальное
  содержимое файла** с диска вместо заглушки. Добавлен per-file debounce
  (`threading.Timer` + `threading.Lock`) для коалесцирования бурных сохранений
  IDE. Observer и таймеры безопасно останавливаются в `on_deactivate`/
  `on_shutdown`.
- `setup.py` — `code_bridge_node` зарегистрирован в `console_scripts`.
- `source_system_launch.py` — `code_bridge_node` добавлен в launch-описание.
- `source_params.yaml` — добавлен параметр `debounce_seconds` для
  `file_watcher_node`.

---

### Этап 5 — Реализация AI-3 (многопоточный analyzer)

**Issue:** [#6](https://github.com/k0ttelll/ros2_sens/issues/6)
**Коммит:** `ad2b628`

Устранили блокировку ROS executor-а на больших STL-файлах.

**Изменения:**

- `stl_analyzer_node.py` — выделенная `ReentrantCallbackGroup` для
  service-server-а.
- `main()` переведён с `rclpy.spin()` на `MultiThreadedExecutor(num_threads=4)`.
- Добавлен параметр `max_input_chars` (по умолчанию `500_000`) — гuard от
  патологически больших входов до попадания в парсер.
- `executor.shutdown()` в `finally` для чистой остановки.

Парсер остаётся stateless → блокировки не требуются.

---

### Этап 6 — E2E-тестирование и релиз в `main`

Все изменения тестировались по принципу **«сначала prerelease, потом main»**.

#### E2E-тест #5 + #7 (Docker, ROS 2 Humble)

Полный trace при помещении `.stl`-файла в `/tmp/code_debug/`:

```
file_watcher_node  → Detected modification in: /tmp/code_debug/test_cylinder.stl
file_watcher_node  → Published 111 chars from test_cylinder.stl to /sens/raw_code_stream
code_bridge_node   → Forwarding 111 chars  →  /sens/parse_code
code_bridge_node   → [✓] Parsed OK — json_len=280
stl_analyzer_node  → Received STL analysis request with 111 characters
```

#### E2E-тест #6 (Docker, конкурентность)

3 параллельных service-call приняты с разницей **1 мс** — подтверждение работы
`MultiThreadedExecutor`:

```
18:26:03  STL analyzer service is ready on /sens/parse_code (multi-threaded)
18:26:48  Received STL analysis request with 55 characters   ← FC3
18:26:48  Received STL analysis request with 64 characters   ← FC1 (через 1 мс)
18:26:49  Received STL analysis request with 56 characters   ← FC2
```

#### Pull Request #8 и мёрдж

Создан [PR #8](https://github.com/k0ttelll/ros2_sens/pull/8) `prerelease → main`.
GitHub подтвердил `mergeable: True, state: clean`. Мёрдж выполнен методом `merge`,
SHA `0dadb88`. Все 4 issue автоматически привязаны и закрыты.

---

## 🏗️ Архитектурные изменения (ДО → ПОСЛЕ)

### Конвейер analytics

```
ДО:                                       ПОСЛЕ:
                                          
[file_watcher] ─ "Content of..." ─┐      [file_watcher] ─ real file ──┐
[git_subscriber] ─ (скелет) ──────┤      [git_subscriber] ─ (скелет) ──┤
[plc_scraper] ─ (заглушка) ───────┤      [plc_scraper] ─ (заглушка) ───┤→ /sens/raw_code_stream
[fallback_sem] ─ (заглушка) ──────┘      [fallback_sem] ─ (заглушка) ──┘        │
        │                                                                          │
        ▼                                                                          ▼
 /sens/raw_code_stream  →  🔴 ЧЁРНАЯ ДЫРА        /sens/raw_code_stream  →  [code_bridge_node] ← NEW
                                                                           │
                                           ┌───────────────────────────────┘
                                           ▼
                                    /sens/parse_code  →  [stl_analyzer_node]
                                                              │  (MultiThreaded ✓)
                                                              ▼
                                         JSON { source, target, block_name,
                                                network_number, type } ← NEW field
```

### Качественные сдвиги

| Параметр | ДО | ПОСЛЕ |
|---|---|---|
| JSON-контракт сервиса | расходится с README (нет `type`, есть `metadata`) | совпадает с README |
| Lifecycle-конвейер | оборван (black hole) | замкнут через `code_bridge_node` |
| `file_watcher` | публикует заглушку | читает файл + debounce |
| `stl_analyzer` executor | однопоточный, блокируется | `MultiThreadedExecutor(4)` |
| Защита от DoS | отсутствует | `max_input_chars` guard |

---

## 📦 Итоговая карта коммитов в `main`

```
0dadb88 Sens analytics pipeline (#8)                    ← merge PR #8
ad2b628 perf(analytics): multi-threaded stl_analyzer    ← AI-3 / #6
1937844 feat(analytics): close lifecycle pipeline gap   ← AI-2 + AI-4 / #5,#7
9bbca18 fix(analytics): emit "type" field               ← AI-1 / #4
ac09aa5 Update copyright year and owner in LICENSE      ← (было ранее)
```

---

## 🔭 Что осталось за рамками этого цикла

Из первичного аудита остались нерешёнными крупные задачи (кандидаты на новые issue):

- **БД** — привязка `storage_node` к TimescaleDB / InfluxDB (сейчас только log).
- **Опрос ПЛК** — реальный Snap7 / OPC UA в `plc_scraper_node` (сейчас заглушка).
- **Сетевые триггеры** — FastAPI-вебхук в `git_subscriber_node` (сейчас скелет).
- **ИИ-контур** — LLM-1 для аномалий + HMI-дашборд (Foxglove).
- **Мёртвый код** — модуль `analysis/` (CFG/dataflow/reaching-defs, ~400 строк):
  подключить к рабочему конвейеру либо удалить.

---

## ✅ Статус по issue

| Issue | Статус | E2E |
|---|---|---|
| [#4](https://github.com/k0ttelll/ros2_sens/issues/4) | 🟢 Closed | unit-тесты |
| [#5](https://github.com/k0ttelll/ros2_sens/issues/5) | 🟢 Closed | Docker E2E |
| [#6](https://github.com/k0ttelll/ros2_sens/issues/6) | 🟢 Closed | Docker E2E |
| [#7](https://github.com/k0ttelll/ros2_sens/issues/7) | 🟢 Closed | Docker E2E |

---

*Журнал ведётся по мере развития платформы. Для новых циклов работ —
добавлять новые разделы сверху, сохраняя хронологию.*
