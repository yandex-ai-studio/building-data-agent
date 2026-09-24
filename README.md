# Создание собственного агента для исследования данных

[English Version](README_en.md)

[Инструкции для воркшопа на SCALE 2026](README_scale.md)

Это репозиторий с материалами к докладу о создании агента для исследования данных с помощью Yandex AI Studio, Responses API и OpenAI Agents SDK.

Доклад состоит из трёх частей:

1. Знакомство с программной работой с LLM при помощи Responses API и OpenAI Agents SDK — откройте [AIStudio_Demo](notebooks/AIStudio_Demo.ipynb) и изучите его.
[![Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/yandex-ai-studio/building-data-agent/blob/main/notebooks/AIStudio_Demo.ipynb)
2. [Опционально] Создание текстовой оболочки для агентов с помощью вайб-кодинга с Codex на основе [Idea File](ideas/text-shell.md)
3. Переход к созданию текстовых консольных агентов для программирования с помощью созданной ранее оболочки, или оболочки [ma](https://github.com/shwars/ma). Она позволяет общаться с любыми агентами, созданными на основе OpenAI Agents SDK, через готовый текстовый интерфейс, похожий на Codex/Claude Code. В каталоге `agents` находится несколько агентов, демонстрирующих различные концепции; их можно запускать непосредственно в среде `ma`.

> Исходный код текстового интерфейса не входит в этот репозиторий, но его всегда можно найти [на GitHub](https://github.com/shwars/ma).

В результате мы создадим агента для исследования данных, который сможет:

1. Брать любые файлы данных (XLSX/CSV) из текущего каталога, исследовать их и загружать в Code Interpreter для обработки.
2. Анализировать эти файлы с помощью Code Interpreter и создавать производные артефакты, включая графики и простые модели машинного обучения.
3. Скачивать полученные артефакты обратно на компьютер пользователя.

## Настройка MA

Сначала необходимо настроить консольную оболочку агентов `ma`. Проще всего сделать это с помощью менеджера пакетов [uv](https://docs.astral.sh/uv/):

1. Установите `uv` ([инструкция](https://docs.astral.sh/uv/getting-started/installation/)):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```
2. Установите `ma` ([инструкция](https://github.com/shwars/ma#run-from-github)):
```bash
uv tool install git+https://github.com/shwars/ma
```
3. Клонируйте этот репозиторий в рабочий каталог:
```bash
git clone https://github.com/shwars/building-data-agent
cd ma-agent
```
`ma` сможет работать с агентами, расположенными в подкаталоге `agents`.
4. Задайте переменные окружения `folder_id` и `api_key` либо поместите в текущий каталог файл `.env` следующего вида:
```
folder_id=...
api_key=...
```
5. Запустите `ma`:
```bash
ma
```
6. Выберите LLM и агента с помощью команд:
```
/model Deepseek V4 Flash
/agent
```
7. Начните диалог — и приятной работы!

## О докладе

Практикум на основе этого репозитория проводился на следующих мероприятиях:

* конференция [Yandex Scale 2026](https://scale.yandex.cloud/) [![GitHub Release](https://img.shields.io/github/v/release/yandex-ai-studio/building-data-agent?filter=v2)](https://github.com/yandex-ai-studio/building-data-agent/tree/v2)
* летняя школа [SMILES-2026](https://smiles.skoltech.ru/) в Сучжоу, Китай [![GitHub Release](https://img.shields.io/github/v/release/yandex-ai-studio/building-data-agent?filter=v1)](https://github.com/yandex-ai-studio/building-data-agent/tree/v1)
