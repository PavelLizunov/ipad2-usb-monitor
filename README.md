# iPad 2 USB Monitor

Дополнительный монитор Omarchy/Hyprland на **iPad 2 GSM (iPad2,2 / K94AP)**:
Linux 6.12 в RAM → USB Ethernet → стандартный VNC → framebuffer 1024×768.

Это рабочий экспериментальный порт для конкретной платы, а не универсальный
установщик Linux. Постоянная установка вместо iOS и сенсорный ввод пока
не реализованы. После полного выключения iPad нужны iOS, активный Carbon
и повторная RAM-загрузка.

## Что работает

- Отдельный экран Hyprland справа от основного, мышь и окна Omarchy.
- Нативные 1024×768; в движении — Tight/JPEG с ARM NEON, после 300 мс
  без обновлений — восстановление кадра без потерь. Уменьшение разрешения
  по умолчанию выключено.
- Ручной поворот на четыре положения: **Super+F8**.
- Переподключение VNC, постоянный USB-профиль NetworkManager и пользовательский
  systemd-сервис. Wi-Fi и браузер не используются.
- Проверка K94AP и идентичности DFU/Recovery перед передачей RAM-образов.

На проверенной анимации 1024×768: около **32–41 обновления/с** в нативном
адаптивном режиме. Статичная область изображения после lossless-refresh
сравнена с источником без отличающихся пикселей. Это не гарантия частоты для
любого содержимого. Подробности — [docs/design.md](docs/design.md).

## Установка на Omarchy / Arch

```sh
sudo pacman -S --needed git uv cmake make binutils python libusb usbmuxd \
  libimobiledevice libusbmuxd openssh wayvnc
git clone https://github.com/PavelLizunov/ipad2-usb-monitor.git
cd ipad2-usb-monitor
./install.sh --boot-kit /path/to/ipad2-k94
ipad-monitor start
```

Installer устанавливает только интеграцию этого монитора; не выполняет полного
обновления системы. Сборка ARM-клиента загружает фиксированные ревизии fbvnc,
libjpeg-turbo, zlib-ng и официальный Zig с проверкой SHA256 в `.build/`.
На подготовленном компьютере доступен `./install.sh --user-only`.

**Boot kit предоставляется отдельно.** В нём должны быть проверенные K94AP
bootchain/bundle, `.work/kloader`, `.work/cascadia/lib/appleusb.py` и свой
авторизованный ключ `.work/ios-root-key`. В этом репозитории нет прошивок,
архивов с ними, приватных ключей и аппаратных дампов. Источник загрузочной
основы: [Project Cascadia](https://github.com/rzxvx/Project-Cascadia).

## Управление

```sh
ipad-monitor start       # в iOS запускает подготовленный RAM-образ
ipad-monitor rotate      # то же, что Super+F8
ipad-monitor portrait
ipad-monitor landscape
ipad-monitor native      # 1024×768, адаптивное восстановление чёткости
ipad-monitor balanced    # 800×600 с растягиванием
ipad-monitor fast        # 640×480: плавнее, но заметно хуже картинка
ipad-monitor quality 10  # постоянный режим без потерь, без автоадаптации
ipad-monitor status
ipad-monitor stop        # останавливает сервер, не выключает iPad
```

Настройки и путь к boot kit: `~/.local/state/ipad2-usb-monitor/`.
Служба: `systemctl --user status ipad2-k94-monitor.service`.
Поддержка сенсора требует отдельного драйвера контроллера и передачи input
в Omarchy; текущий kernel не обнаруживает input-устройств планшета.

## Авторство

Код управления, USB-интеграция, K94-адаптер и изменения клиента создавались
в проекте Павла Лизунова с помощью Codex. Основа — сторонние свободные проекты;
их авторство и лицензии перечислены в [THIRD_PARTY.md](THIRD_PARTY.md).
Свой код — MIT; лицензии производных патчей указаны отдельно.
