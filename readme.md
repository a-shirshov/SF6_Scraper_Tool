# SF6 League Points tool

## Как запускать

У вас должен быть python3 - я писал на версии 3.12

У вас должен быть менеджер пакетов - pip, например

Установка зависимостей:

```
pip install -r /path/to/requirements.txt
```

В файле cfn_list.txt указать необходимые для поиска cfn в формате:

```
PlayerCFN1
PlayerCFN2
PlayerCFN3
```

В репозитории лежит драйвер firefox для win64

При необходимости можно заменить, но писалось под него.

В коде есть переменная, отвечающая за путь к драйверу

## Работа с программой

Создать файл .env и выставить нужные значения (опирайтесь на .env.example)

запустить скрипт:

```sh
python3 ./scraper.py
```

В начале работы можно указать требования по кол-ву матчей и максимальному кол-ву поинтов.
В случае обнаружения игрока, не соответствующего ограничениям он будет подсвечен красным.
Также в случае работы с чалонгом идёт проверка на совпадение ника игрока.

Если указан некорректный cfn - эти данные укажутся в файле bad players

После этого откроется окно браузера

1. Сначала будет процесс авторизации на сайте
2. После него начнётся сбор данных по указанным CFN
3. Результатом будет excel файл с собранными данными

## Возможные улучшения

1. Добавление в отчёт кол-во матчей - сделано
2. Уменьшение копипасты, time.sleep, разбиение на файлы, с for на range - я не питонист, увы
3. Подкрасить легким цветом ранги даймонд, платина, чтобы было проще визуализировать
4. Venv мб - но вроде не нужен
5. Если получится просто запросами без селениума, то будет быстрее, но тогда я всё делал зря. Однако, будет кайф)
