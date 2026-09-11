$(document).ready(function () {
    /*
    window.dataTable = $('table:not(.no-datatables)').DataTable({
        language: {
            "processing": "Подождите...",
            "search": "Поиск:",
            "lengthMenu": "Показать _MENU_ записей",
            "info": "Записи с _START_ до _END_ из _TOTAL_ записей",
            "infoEmpty": "Записи с 0 до 0 из 0 записей",
            "infoFiltered": "(отфильтровано из _MAX_ записей)",
            "loadingRecords": "Загрузка записей...",
            "zeroRecords": "Записи отсутствуют.",
            "emptyTable": "В таблице отсутствуют данные",
            "paginate": {
                "first": "Первая",
                "previous": "Предыдущая",
                "next": "Следующая",
                "last": "Последняя"
            },
            "aria": {
                "sortAscending": ": активировать для сортировки столбца по возрастанию",
                "sortDescending": ": активировать для сортировки столбца по убыванию"
            },
            "select": {
                "rows": {
                    "_": "Выбрано записей: %d",
                    "1": "Выбрана одна запись"
                },
                "cells": {
                    "_": "Выбрано %d ячеек",
                    "1": "Выбрана 1 ячейка "
                },
                "columns": {
                    "1": "Выбран 1 столбец ",
                    "_": "Выбрано %d столбцов "
                }
            },
            "searchBuilder": {
                "conditions": {
                    "string": {
                        "startsWith": "Начинается с",
                        "contains": "Содержит",
                        "empty": "Пусто",
                        "endsWith": "Заканчивается на",
                        "equals": "Равно",
                        "not": "Не",
                        "notEmpty": "Не пусто",
                        "notContains": "Не содержит",
                        "notStartsWith": "Не начинается на",
                        "notEndsWith": "Не заканчивается на"
                    },
                    "date": {
                        "after": "После",
                        "before": "До",
                        "between": "Между",
                        "empty": "Пусто",
                        "equals": "Равно",
                        "not": "Не",
                        "notBetween": "Не между",
                        "notEmpty": "Не пусто"
                    },
                    "number": {
                        "empty": "Пусто",
                        "equals": "Равно",
                        "gt": "Больше чем",
                        "gte": "Больше, чем равно",
                        "lt": "Меньше чем",
                        "lte": "Меньше, чем равно",
                        "not": "Не",
                        "notEmpty": "Не пусто",
                        "between": "Между",
                        "notBetween": "Не между ними"
                    },
                    "array": {
                        "equals": "Равно",
                        "empty": "Пусто",
                        "contains": "Содержит",
                        "not": "Не равно",
                        "notEmpty": "Не пусто",
                        "without": "Без"
                    }
                },
                "data": "Данные",
                "deleteTitle": "Удалить условие фильтрации",
                "logicAnd": "И",
                "logicOr": "Или",
                "title": {
                    "0": "Конструктор поиска",
                    "_": "Конструктор поиска (%d)"
                },
                "value": "Значение",
                "add": "Добавить условие",
                "button": {
                    "0": "Конструктор поиска",
                    "_": "Конструктор поиска (%d)"
                },
                "clearAll": "Очистить всё",
                "condition": "Условие",
                "leftTitle": "Превосходные критерии",
                "rightTitle": "Критерии отступа"
            },
            "searchPanes": {
                "clearMessage": "Очистить всё",
                "collapse": {
                    "0": "Панели поиска",
                    "_": "Панели поиска (%d)"
                },
                "count": "{total}",
                "countFiltered": "{shown} ({total})",
                "emptyPanes": "Нет панелей поиска",
                "loadMessage": "Загрузка панелей поиска",
                "title": "Фильтры активны - %d",
                "showMessage": "Показать все",
                "collapseMessage": "Скрыть все"
            },
            "buttons": {
                "pdf": "PDF",
                "print": "Печать",
                "collection": "Коллекция <span class=\"ui-button-icon-primary ui-icon ui-icon-triangle-1-s\"><\/span>",
                "colvis": "Видимость столбцов",
                "colvisRestore": "Восстановить видимость",
                "copy": "Копировать",
                "copyTitle": "Скопировать в буфер обмена",
                "csv": "CSV",
                "excel": "Excel",
                "pageLength": {
                    "-1": "Показать все строки",
                    "_": "Показать %d строк",
                    "1": "Показать 1 строку"
                },
                "removeState": "Удалить",
                "renameState": "Переименовать",
                "copySuccess": {
                    "1": "Строка скопирована в буфер обмена",
                    "_": "Скопировано %d строк в буфер обмена"
                },
                "createState": "Создать состояние",
                "removeAllStates": "Удалить все состояния",
                "savedStates": "Сохраненные состояния",
                "stateRestore": "Состояние %d",
                "updateState": "Обновить",
                "copyKeys": "Нажмите ctrl  или u2318 + C, чтобы скопировать данные таблицы в буфер обмена.  Для отмены, щелкните по сообщению или нажмите escape."
            },
            "decimal": ".",
            "infoThousands": ",",
            "autoFill": {
                "cancel": "Отменить",
                "fill": "Заполнить все ячейки <i>%d<i><\/i><\/i>",
                "fillHorizontal": "Заполнить ячейки по горизонтали",
                "fillVertical": "Заполнить ячейки по вертикали",
                "info": "Информация"
            },
            "datetime": {
                "previous": "Предыдущий",
                "next": "Следующий",
                "hours": "Часы",
                "minutes": "Минуты",
                "seconds": "Секунды",
                "unknown": "Неизвестный",
                "amPm": [
                    "AM",
                    "PM"
                ],
                "months": {
                    "0": "Январь",
                    "1": "Февраль",
                    "10": "Ноябрь",
                    "11": "Декабрь",
                    "2": "Март",
                    "3": "Апрель",
                    "4": "Май",
                    "5": "Июнь",
                    "6": "Июль",
                    "7": "Август",
                    "8": "Сентябрь",
                    "9": "Октябрь"
                },
                "weekdays": [
                    "Вс",
                    "Пн",
                    "Вт",
                    "Ср",
                    "Чт",
                    "Пт",
                    "Сб"
                ]
            },
            "editor": {
                "close": "Закрыть",
                "create": {
                    "button": "Новый",
                    "title": "Создать новую запись",
                    "submit": "Создать"
                },
                "edit": {
                    "button": "Изменить",
                    "title": "Изменить запись",
                    "submit": "Изменить"
                },
                "remove": {
                    "button": "Удалить",
                    "title": "Удалить",
                    "submit": "Удалить",
                    "confirm": {
                        "_": "Вы точно хотите удалить %d строк?",
                        "1": "Вы точно хотите удалить 1 строку?"
                    }
                },
                "multi": {
                    "restore": "Отменить изменения",
                    "title": "Несколько значений",
                    "info": "Выбранные элементы содержат разные значения для этого входа. Чтобы отредактировать и установить для всех элементов этого ввода одинаковое значение, нажмите или коснитесь здесь, в противном случае они сохранят свои индивидуальные значения.",
                    "noMulti": "Это поле должно редактироваться отдельно, а не как часть группы"
                },
                "error": {
                    "system": "Возникла системная ошибка (<a target=\"\\\" rel=\"nofollow\" href=\"\\\">Подробнее<\/a>)."
                }
            },
            "searchPlaceholder": "Что ищете?",
            "stateRestore": {
                "creationModal": {
                    "button": "Создать",
                    "search": "Поиск",
                    "columns": {
                        "search": "Поиск по столбцам",
                        "visible": "Видимость столбцов"
                    },
                    "name": "Имя:",
                    "order": "Сортировка",
                    "paging": "Страницы",
                    "scroller": "Позиция прокрутки",
                    "searchBuilder": "Редактор поиска",
                    "select": "Выделение",
                    "title": "Создать новое состояние",
                    "toggleLabel": "Включает:"
                },
                "removeJoiner": "и",
                "removeSubmit": "Удалить",
                "renameButton": "Переименовать",
                "duplicateError": "Состояние с таким именем уже существует.",
                "emptyError": "Имя не может быть пустым.",
                "emptyStates": "Нет сохраненных состояний",
                "removeConfirm": "Вы уверены, что хотите удалить %s?",
                "removeError": "Не удалось удалить состояние.",
                "removeTitle": "Удалить состояние",
                "renameLabel": "Новое имя для %s:",
                "renameTitle": "Переименовать состояние"
            },
            "thousands": " "
        },
    });
    */

    if (window.dataTable) {
        $('.column-toggle').each(function () {
            var column = window.dataTable.column($(this).data('column'));
            var storedState = localStorage.getItem('column-' + $(this).data('column'));
            if (storedState !== null) {
                var isChecked = (storedState === 'true');
                $(this).prop('checked', isChecked);
                column.visible(isChecked);
            } else {
                // По умолчанию показываем все колонки
                $(this).prop('checked', true);
                column.visible(true);
            }
        });

        // Обработка события изменения состояния чекбоксов
        $('.column-toggle').change(function () {
            var column = window.dataTable.column($(this).data('column'));
            var isVisible = $(this).is(':checked');
            column.visible(isVisible);
            // Сохранение состояния в localStorage
            localStorage.setItem('column-' + $(this).data('column'), isVisible);
        });
    }

    if ($.fn.modal) {
        $('.modal').modal({
            show: false
        });
    }

    (function () {
        const POLL_INTERVAL = 30000;  // 30 сек
        const badgeEl = document.getElementById('notif-badge');
        const listEl  = document.getElementById('notif-list');
        const emptyEl = document.getElementById('notif-empty');
        const markAllBtn = document.getElementById('mark-all-read');

        if (!badgeEl) return;  // не авторизован — выходим

        function getCookie(name) {
            const v = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
            return v ? v.pop() : '';
        }

        function renderNotifications(data) {
            // Бейдж
            if (data.unread_count > 0) {
                badgeEl.textContent = data.unread_count > 99 ? '99+' : data.unread_count;
                badgeEl.style.display = '';
            } else {
                badgeEl.style.display = 'none';
            }

            // Список
            listEl.innerHTML = '';
            if (!data.notifications.length) {
                emptyEl.style.display = '';
                return;
            }
            emptyEl.style.display = 'none';

            data.notifications.forEach(n => {
                const a = document.createElement('a');
                a.className = 'notif-item' + (n.is_read ? '' : ' unread');
                a.href = n.url || '#';
                a.dataset.id = n.id;

                const title = document.createElement('div');
                title.className = 'notif-title';
                if (!n.is_read) {
                    const dot = document.createElement('span');
                    dot.className = 'notif-dot';
                    title.appendChild(dot);
                }
                title.appendChild(document.createTextNode(n.title || 'Уведомление'));
                a.appendChild(title);

                if (n.message) {
                    const msg = document.createElement('div');
                    msg.className = 'notif-msg';
                    msg.textContent = n.message;
                    a.appendChild(msg);
                }

                const time = document.createElement('div');
                time.className = 'notif-time';
                time.textContent = n.created_at;
                a.appendChild(time);

                a.addEventListener('click', function (e) {
                    // Помечаем прочитанным, потом переходим
                    if (!n.is_read) {
                        fetch(`/api/notifications/${n.id}/read/`, {
                            method: 'POST',
                            headers: {'X-CSRFToken': getCookie('csrftoken')},
                        }).catch(() => {});
                        a.classList.remove('unread');
                        const dot = a.querySelector('.notif-dot');
                        if (dot) dot.remove();
                    }
                    if (!n.url) {
                        e.preventDefault();  // если ссылки нет — не переходим
                    }
                });

                const wrapper = document.createElement('div');
                wrapper.className = 'notif-wrapper position-relative';

                wrapper.appendChild(a);

                const delBtn = document.createElement('button');
                delBtn.className = 'notif-delete-btn';
                delBtn.title = 'Удалить';
                delBtn.innerHTML = '&times;';
                delBtn.addEventListener('click', function (e) {
                    e.preventDefault();
                    e.stopPropagation();
                    fetch(`/api/notifications/${n.id}/delete/`, {
                        method: 'POST',
                        headers: {'X-CSRFToken': getCookie('csrftoken')},
                    })
                    .then(() => loadNotifications())
                    .catch(() => {});
                });
                wrapper.appendChild(delBtn);

                listEl.appendChild(wrapper);
            });
        }

        function loadNotifications() {
            fetch('/api/notifications/')
                .then(r => r.json())
                .then(renderNotifications)
                .catch(() => {});  // тихо игнорим сетевые ошибки
        }

        markAllBtn.addEventListener('click', function (e) {
            e.preventDefault();
            e.stopPropagation();
            fetch('/api/notifications/read-all/', {
                method: 'POST',
                headers: {'X-CSRFToken': getCookie('csrftoken')},
            })
            .then(() => loadNotifications())
            .catch(() => {});
        });

        // Первый запрос сразу, потом опрос по таймеру
        loadNotifications();
        setInterval(loadNotifications, POLL_INTERVAL);

        // Обновляем, когда пользователь открывает дропдаун (чтобы было свежее)
        document.getElementById('notifDropdown')
            ?.addEventListener('shown.bs.dropdown', loadNotifications);

        const deleteAllBtn = document.getElementById('delete-all-notif');

        if (deleteAllBtn) {
            deleteAllBtn.addEventListener('click', function (e) {
                e.preventDefault();
                e.stopPropagation();

                if (!confirm('Удалить все уведомления?')) return;

                fetch('/api/notifications/delete-all/', {
                    method: 'POST',
                    headers: {'X-CSRFToken': getCookie('csrftoken')},
                })
                .then(r => r.json())
                .then(() => loadNotifications())
                .catch(() => {});
            });
        }
    })();
});

