# door-view

Домашняя система видеонаблюдения для двери/участка на базе Raspberry Pi + IP-камеры по RTSP. Пишет видео только когда есть движение, отдаёт живой просмотр в браузере через HLS, хранит записи на USB-флешке и сама следит за свободным местом.

Сделано для одной конкретной дачи/двери, но легко переиспользуется под любую RTSP-камеру и любой Linux-хост (не обязательно Pi).

## Возможности

- **Живой просмотр** в браузере (HLS через ffmpeg + hls.js), работает и на телефоне
- **Запись по движению** (детектор MOG2 на OpenCV) вместо записи 24/7 – экономит место
- **Fragmented MP4** – если питание/процесс упадёт посреди записи, файл всё равно проигрывается
- **Автоочистка диска** – если свободного места меньше порога, удаляются самые старые записи
- **Веб-страница со списком записей** – просмотр и скачивание прямо из браузера
- **Автовосстановление**: systemd перезапускает сервис при падении, ffmpeg-процессы сами переподключаются при обрыве RTSP
- **Еженедельный перезапуск Pi по таймеру** – на всякий случай, для стабильности

## Как это работает

Камера отдаёт два RTSP-потока: основной (высокое разрешение) и субпоток (низкое разрешение). Это стандартная фича IP-камер видеонаблюдения, и она здесь ключевая:

- **Основной поток** (`CAMERA_INDEX`) идёт на HLS-стрим и на запись – тут важно качество
- **Субпоток** (`DETECTION_INDEX`) идёт на детект движения – тут важна дешевизна по CPU, а разрешение не имеет значения

Внутри `Camera` крутятся несколько потоков/процессов:

1. **HLS-процесс ffmpeg** – постоянно транслирует основной поток в HLS-сегменты (`-c copy`, без перекодирования, почти не грузит CPU)
2. **Capture-поток** – читает кадры из субпотока в общий буфер
3. **Detect-поток** – гоняет MOG2 по кадрам из буфера, при движении запускает запись, при `MOTION_COOLDOWN` секундах без движения – останавливает
4. **Recording-процесс ffmpeg** – отдельный ffmpeg на каждую запись, тоже `-c copy`, с флагами `frag_keyframe+empty_moov` для fragmented MP4
5. **Storage-monitor поток** – раз в 10 минут проверяет свободное место, при нехватке удаляет старые `.mp4` (не больше 10 файлов за раз, чтобы не полохо в бесконечный цикл)

Все ffmpeg-процессы и потоки при обрыве связи с камерой сами переподключаются с задержкой, а не убивают всё приложение.

## Стек

- Python 3 + Flask – веб-сервер и роуты
- OpenCV (`opencv-python-headless`) – только для детекта движения (MOG2)
- ffmpeg (системный бинарник, вызывается через `subprocess`) – HLS-стрим и запись
- hls.js – плеер HLS на фронтенде
- systemd – автозапуск, автоперезапуск, еженедельный ребут

## Структура проекта

```
door-view/
├── src/
│   ├── main.py          # Flask-приложение, роуты
│   ├── camera.py        # вся логика камеры: HLS, детект, запись, чистка диска
│   ├── config.py        # конфиг (см. ниже)
│   ├── utils.py         # мелкие хелперы (таймстемп для имён файлов)
│   ├── templates/
│   │   ├── index.html   # страница живого просмотра
│   │   └── records.html # страница со списком записей
│   └── static/
│       ├── script.js    # логика hls.js плеера
│       └── style.css
├── __pycache__/		 # кэш, не хранится в репо
└── venv/                # создаётся при установке, не хранится в репо
```

## Требования

- Raspberry Pi (тестировалось на **4B**) или любой Linux-хост с достаточным CPU под ffmpeg copy-режим
- IP-камера с RTSP, желательно с двумя потоками (main + sub)
- USB-флешка/SSD для хранения записей (SD-карта Pi для этого не годится – убьётся по ресурсу записи)
- Пакеты: `ffmpeg`, `python3-opencv`, `python3-pip`, `python3-venv`

---

## Установка с нуля

### 1. Прошить SD-карту

Raspberry Pi Imager → **Raspberry Pi OS Lite** → записать на карту.

### 2. Подключиться по SSH

Найти IP Pi в роутере:

```bash
ssh pi@<ip-малинки>
```

### 3. Найти и проверить RTSP-потоки камеры

Найти IP камеры в роутере. URL потоков собирается вручную – порт и путь зависят от модели, смотреть в веб-морде камеры:

```
rtsp://<user>:<password>@<ip-камеры>/stream1   # основной, высокое разрешение
rtsp://<user>:<password>@<ip-камеры>/stream0   # субпоток, низкое разрешение
```

Проверить, что потоки реально отдают видео:

```bash
ffmpeg -rtsp_transport tcp -i "rtsp://<user>:<password>@<ip-камеры>/stream1" -t 5 test.mp4
ffmpeg -rtsp_transport tcp -i "rtsp://<user>:<password>@<ip-камеры>/stream0" -t 5 test0.mp4
```

### 4. Установить системные зависимости

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install ffmpeg python3-opencv python3-pip python3-venv git -y
```

### 5. Клонировать репозиторий

```bash
git clone https://github.com/xzbey/door-view ~/door-view
cd ~/door-view/src
```

### 6. Виртуальное окружение и python-зависимости

```bash
python3 -m venv venv
source venv/bin/activate
pip install flask opencv-python-headless
```

### 7. Подключить и смонтировать флешку для записей

```bash
lsblk   # найти устройство, например /dev/sda1
sudo mkdir -p /mnt/storage
sudo mount /dev/sda1 /mnt/storage
```

Чтобы флешка монтировалась автоматически при загрузке, добавить в `/etc/fstab`:

```
/dev/sda1  /mnt/storage  vfat  defaults,noatime  0  2
```

### 8. Настроить `config.py`

```python
CAMERA_INDEX = "rtsp://<user>:<password>@<ip-камеры>/stream1"
DETECTION_INDEX = "rtsp://<user>:<password>@<ip-камеры>/stream0"
STORAGE_PATH = "/mnt/storage"
```

Остальные параметры – по вкусу, см. таблицу конфига ниже.

### 9. Ручной запуск для проверки

```bash
cd ~/door-view/src
source venv/bin/activate
python main.py
```

Открыть в браузере: `http://<ip-малинки>:5000`

### 10. Автозапуск через systemd

```bash
sudo nano /etc/systemd/system/door-view.service
```

```ini
[Unit]
Description=door-view surveillance
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/door-view/src
ExecStart=/home/pi/door-view/src/venv/bin/python main.py
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable door-view
sudo systemctl start door-view
```

Проверить:

```bash
sudo systemctl status door-view
journalctl -u door-view -f
```

Перезапустить после изменений в коде:

```bash
sudo systemctl restart door-view
```

### 11. Еженедельный автоматический перезапуск Pi

Полезно для долгосрочной стабильности – раз в неделю чистый ребут.

Узнать путь к `reboot` (пригодится в юните):

```bash
which reboot
```

```bash
sudo nano /etc/systemd/system/weekly-reboot.service
```

```ini
[Unit]
Description=Weekly reboot

[Service]
Type=oneshot
ExecStart=/usr/sbin/reboot
```

*(подставить реальный путь из `which reboot`, если отличается)*

```bash
sudo nano /etc/systemd/system/weekly-reboot.timer
```

```ini
[Unit]
Description=Weekly reboot timer

[Timer]
OnCalendar=Sun *-*-* 04:00:00

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now weekly-reboot.timer
```

Проверить, что таймер встал:

```bash
systemctl list-timers | grep weekly-reboot
```

### 12. Настроить постоянный журнал systemd

По умолчанию journald хранит логи только в RAM и теряет их при перезагрузке. Чтобы логи не исчезали:

```bash
sudo nano /etc/systemd/journald.conf
```

```ini
[Journal]
Storage=persistent
MaxRetentionSec=2week
SystemMaxUse=200M
```

```bash
sudo systemctl restart systemd-journald
```

### 13. Веб-морда самой камеры

Зайти на IP камеры в браузере → раздел вроде Maintenance / Auto Reboot → поставить перезагрузку раз в неделю (аналогично Pi, но средствами самой камеры).

---

## Конфигурация (`config.py`)

| Параметр | Что делает |
|---|---|
| `CAMERA_INDEX` | RTSP-адрес основного потока (HLS + запись) |
| `DETECTION_INDEX` | RTSP-адрес субпотока (детект движения) |
| `SAVE_MODE` | включает/выключает весь пайплайн детекта и записи (при `False` – только живой стрим) |
| `MIN_FREE_GB` | порог свободного места на флешке, ниже которого начинают удаляться старые записи |
| `PORT` | порт Flask-сервера |
| `STORAGE_PATH` | абсолютный путь к смонтированной флешке |
| `HLS_PATH` | подпапка внутри `STORAGE_PATH` для HLS-сегментов |
| `MOTION_COOLDOWN` | сколько секунд без движения ждать перед остановкой записи |
| `MOTION_MIN_AREA` | минимальная площадь контура (px²), чтобы засчитать движение |
| `MOTION_VAR_THRESHOLD` | чувствительность MOG2 (порог дисперсии) |
| `MOTION_HISTORY` | размер истории кадров для MOG2 (и длина фазы прогрева) |

## Веб-роуты

| Роут | Что делает |
|---|---|
| `GET /` | страница живого просмотра |
| `GET /stream/<filename>` | отдаёт HLS-плейлист и сегменты |
| `GET /records` | список записей с сортировкой по дате |
| `GET /records/<filename>` | открыть запись в браузере |
| `GET /records/<filename>?dl=1` | скачать запись как файл |

## Известные микро траблы

- **Флаг `-stimeout` у ffmpeg** – в некоторых сборках ffmpeg этого флага нет, используется `-timeout` (уже так в коде; `-stimeout` оставлен закомментированным как напоминание, если попадётся другая версия ffmpeg)
- **SD-карта Pi не для записей** – весь пайплайн пишет только на `STORAGE_PATH` (флешка/SSD), но если вдруг STORAGE_PATH случайно указать на саму SD-карту – она быстро деградирует от постоянной записи
- **Обрыв RTSP** – оба ffmpeg-процесса (HLS и capture-поток) сами переподключаются с задержкой, это нормальное поведение, не баг, если видно в логах периодические "reconnecting"

## Возможные доработки

- Дополнение системы: BME280 (температура/влажность) через I2C для дополнения системы данными с датчика
- Бесперебойная работа: ИБП + стабилизатор напряжения для питания Pi на даче (защита от скачков/пропаданий питания)
