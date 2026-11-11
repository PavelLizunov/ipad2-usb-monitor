# Сторонние компоненты и границы авторства

| Компонент | Роль | Лицензия / источник |
| --- | --- | --- |
| Linux 6.12 / Project Cascadia | ядро и основа RAM boot | GPL-2.0, https://github.com/rzxvx/Project-Cascadia |
| fbvnc, Ali Gholami Rudi | основа framebuffer VNC-клиента | ISC; [текст](licenses/fbvnc-ISC.txt), https://github.com/aligrudi/fbvnc |
| WayVNC / neatvnc | сервер захвата экрана | ISC, https://github.com/any1/wayvnc, https://github.com/any1/neatvnc |
| libjpeg-turbo | JPEG и ARM NEON | BSD-style / IJG / zlib, https://github.com/libjpeg-turbo/libjpeg-turbo |
| zlib-ng | lossless DEFLATE / NEON | zlib, https://github.com/zlib-ng/zlib-ng |
| Zig | кросс-компилятор и musl toolchain | MIT и лицензии включённых компонентов, https://ziglang.org |
| PyUSB / pySerial | USB и консоль | BSD / BSD, https://github.com/pyusb/pyusb, https://github.com/pyserial/pyserial |

`patches/fbvnc-monitor.patch` — изменения поверх fbvnc с сохранением его ISC
лицензии и авторства. `patches/cascadia-k94-bootchain.patch` — производные
изменения GPL-2.0; [исходная лицензия](licenses/Project-Cascadia-GPL-2.0.txt).
Свой код управления и диагностического устройства распространяется по MIT.

Нельзя приписывать этому проекту авторство ядра, исходного загрузочного порта,
VNC-протокола, fbvnc и библиотек. Здесь разработаны интеграция, адаптер K94,
проверки идентичности/возобновления, управление жизненным циклом и расширения
клиента: Tight/JPEG, NEON-преобразование пикселей, буферизация, адаптивный
lossless-refresh, масштабирование и поворот.

Исходники зависимостей загружаются сборщиком вместе с их лицензиями в `.build/`.
Фиксированные ревизии записаны в `tools/build_viewer.py`. Системные WayVNC и
neatvnc не модифицируются. Apple-компоненты и их бинарники сюда не входят.
