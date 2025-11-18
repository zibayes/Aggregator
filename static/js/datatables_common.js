// Функция для получения CSRF токена
function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

// Русская локализация для DataTables
const datatablesRussianLocale = {
    "emptyTable": "В таблице отсутствуют данные",
    "info": "Записи с _START_ до _END_ из _TOTAL_ записей",
    "infoEmpty": "Записи с 0 до 0 из 0 записей",
    "infoFiltered": "(отфильтровано из _MAX_ записей)",
    "infoPostFix": "",
    "thousands": " ",
    "lengthMenu": "Показать _MENU_ записей",
    "loadingRecords": "Загрузка...",
    "processing": "Подождите...",
    "search": "Поиск:",
    "zeroRecords": "Записи отсутствуют.",
    "paginate": {
        "first": "Первая",
        "last": "Последняя",
        "next": "Следующая",
        "previous": "Предыдущая"
    },
    "aria": {
        "sortAscending": ": активировать для сортировки столбца по возрастанию",
        "sortDescending": ": активировать для сортировки столбца по убыванию"
    }
};

// Базовые настройки DataTables
// Базовые настройки DataTables
const datatablesBaseConfig = {
    "processing": true,
    "serverSide": true,
    "language": datatablesRussianLocale,
    "dom": '<"row"<"col-sm-12 col-md-6"l><"col-sm-12 col-md-6"f>>rt<"row"<"col-sm-12 col-md-5"i><"col-sm-12 col-md-7"p>>',
    "pageLength": 10,
    "lengthMenu": [10, 25, 50, 100],
    "responsive": true,
    "autoWidth": false,
    "initComplete": function(settings, json) {
        // Восстанавливаем заголовки из HTML
        const thead = this.api().table().header();
        $(thead).find('th').each(function(i) {
            const originalTitle = $(this).text();
            if (originalTitle && settings.aoColumns[i]) {
                settings.aoColumns[i].sTitle = originalTitle;
            }
        });
    }
};

// Функция безопасной инициализации DataTable
function initializeDataTable(config) {
    console.log("Initializing DataTable...");

    // Уничтожаем существующую таблицу если есть
    if ($.fn.DataTable.isDataTable('.table')) {
        console.log("Destroying existing DataTable...");
        $('.table').DataTable().destroy();
    }

    // Восстанавливаем оригинальные заголовки из HTML
    const originalHeaders = [];
    $('.table thead th').each(function() {
        originalHeaders.push($(this).text().trim());
    });

    console.log("Original headers:", originalHeaders);

    // Добавляем заголовки к колонкам
    if (config.columns && originalHeaders.length > 0) {
        config.columns.forEach((col, index) => {
            if (originalHeaders[index]) {
                col.title = originalHeaders[index];
            }
        });
    }

    // Объединяем базовые настройки с переданными
    const finalConfig = {
        ...datatablesBaseConfig,
        ...config
    };

    console.log("Final DataTable config:", finalConfig);

    // Создаем новую таблицу
    const table = $('.table').DataTable(finalConfig);

    console.log("DataTable initialized successfully");
    return table;
}

// Функция для настройки фильтров
function setupFilters(table, filterConfigs) {
    function applyFilters() {
        console.log("Applying filters...");
        table.ajax.reload();
    }

    // Настройка текстовых фильтров
    filterConfigs.textFilters.forEach(selector => {
        $(selector).on('keyup', function() {
            applyFilters();
        });
    });

    // Настройка выпадающих фильтров и чекбоксов
    filterConfigs.changeFilters.forEach(selector => {
        $(selector).on('change', function() {
            applyFilters();
        });
    });

    return applyFilters;
}

// Функция для настройки переключателей колонок
function setupColumnToggles(table) {
    function updateColumnVisibility() {
        $('.column-toggle').each(function() {
            const columnIndex = parseInt($(this).data('column'));
            const isVisible = $(this).is(':checked');
            table.column(columnIndex).visible(isVisible);
        });
    }

    $('.column-toggle').on('change', function() {
        updateColumnVisibility();
    });

    // Инициализация видимости колонок при загрузке
    updateColumnVisibility();
}

// Универсальная функция инициализации
function setupDataTable(tableConfig) {
    const table = initializeDataTable(tableConfig);

    if (tableConfig.filterConfigs) {
        setupFilters(table, tableConfig.filterConfigs);
    }

    setupColumnToggles(table);

    console.log("DataTable setup completed, returning instance:", table);
    return table;
}

// Добавь эти стили в твой CSS файл или в <style> в шаблоне
const sortStyles = `
<style>
table.dataTable thead .sorting:after { content: "⇅"; opacity: 0.3; float: right; }
table.dataTable thead .sorting_asc:after { content: "↑"; float: right; }
table.dataTable thead .sorting_desc:after { content: "↓"; float: right; }
table.dataTable thead .sorting_asc_disabled:after { content: "↑"; opacity: 0.3; float: right; }
table.dataTable thead .sorting_desc_disabled:after { content: "↓"; opacity: 0.3; float: right; }
</style>
`;

// Добавь стили в документ
document.head.insertAdjacentHTML('beforeend', sortStyles);

// Универсальная функция для модального окна удаления
let currentDeleteData = null;

function openDeleteModal(objectId, objectName, modalType) {
    currentDeleteData = {
        id: objectId,
        name: objectName,
        type: modalType
    };

    objectName = objectName.replace(/\r\n/g, ' ').replace(/\n/g, ' ').replace(/\t+/g, ' ').replace(/ +/g, ' ').trim();
    document.getElementById('deleteObjectName').textContent = objectName;

    const deleteModal = new bootstrap.Modal(document.getElementById('deleteModal'));
    deleteModal.show();
}

function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]').getAttribute('content');
}

function confirmDelete() {
    if (!currentDeleteData) return;

    const deleteFiles = document.getElementById('deleteFilesCheckbox').checked;
    const csrfToken = getCSRFToken();

    // Создаем форму динамически
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = getDeleteUrl(currentDeleteData);

    // Добавляем CSRF токен
    const csrfInput = document.createElement('input');
    csrfInput.type = 'hidden';
    csrfInput.name = 'csrfmiddlewaretoken';
    csrfInput.value = csrfToken;
    form.appendChild(csrfInput);

    // Добавляем флаг удаления файлов
    if (deleteFiles) {
        const filesInput = document.createElement('input');
        filesInput.type = 'hidden';
        filesInput.name = 'delete_files';
        filesInput.value = 'on';
        form.appendChild(filesInput);
    }

    document.body.appendChild(form);
    form.submit();
}

function getDeleteUrl(deleteData) {
    const urlMap = {
        'delete_act': `/acts_delete/${deleteData.id}/`,
        'delete_scientific_report': `/scientific_reports_delete/${deleteData.id}/`,
        'delete_tech_report': `/tech_reports_delete/${deleteData.id}/`,
        'delete_open_list': `/open_lists_delete/${deleteData.id}/`,
        'delete_archaeological_heritage_site': `/archaeological_heritage_sites_delete/${deleteData.id}/`,
        'delete_identified_site': `/identified_archaeological_heritage_sites_delete/${deleteData.id}/`,
        'delete_account_card': `/account_cards_delete/${deleteData.id}/`,
        'delete_commercial_offer': `/commercial_offers_delete/${deleteData.id}/`,
        'delete_geo_object': `/geo_objects_delete/${deleteData.id}/`
    };

    return urlMap[deleteData.type] || '#';
}

// Глобальная переменная для DataTable
let dataTableInstance = null;

// Универсальная конфигурация DataTable
function setupHeritageDataTable(config) {
    $(document).ready(function() {
        const tableConfig = {
            "ajax": {
                "url": config.url,
                "type": "POST",
                "headers": {
                    'X-CSRFToken': getCookie('csrftoken')
                },
                "data": function (d) {
                    // Добавляем параметр хранилища в фильтры
                    const filters = config.getFilters();
                    filters.storage_type = getStorageType();
                    d.custom_search = JSON.stringify(filters);
                },
                "dataSrc": "data",
                "error": function (xhr, error, thrown) {
                    console.log("DataTables AJAX error:", error);
                    console.log("XHR status:", xhr.status);
                    console.log("XHR response:", xhr.responseText);
                }
            },
            "columns": config.columns,
            "filterConfigs": config.filterConfigs
        };

        // Инициализируем DataTable и сохраняем ссылку
        dataTableInstance = setupDataTable(tableConfig);
    });
}

// Функции для работы с хранилищем
function getStorageType() {
    const storageSwitch = document.getElementById('storageSwitch');
    return storageSwitch && storageSwitch.checked ? 'private' : 'public';
}

function updateStorageLabel() {
    const storageSwitch = document.getElementById('storageSwitch');
    const storageLabel = document.getElementById('storageLabel');
    if (storageSwitch && storageLabel) {
        const isPrivate = storageSwitch.checked;
        storageLabel.textContent = isPrivate ? "Частное хранилище" : "Публичное хранилище";
    }
}

function reloadDataTable() {
    if (dataTableInstance) {
        dataTableInstance.ajax.reload();
    } else {
        console.warn('DataTable not initialized yet');
    }
}

// Функция для обновления видимости фильтров (только для статических таблиц)
function updateFilterVisibility() {
    if (window.usesAjax) return;

    let columnToggles = document.querySelectorAll('.column-toggle');
    let filterForm = document.getElementById('filterForm');

    columnToggles.forEach(toggle => {
        let columnIndex = toggle.getAttribute('data-column');
        let columns_count = parseInt(toggle.closest('[data-columns-count]').dataset.columnsCount);

        if (columnIndex >= filterForm.children.length) {
            return;
        }

        let filterContainer = filterForm.children[columnIndex];
        if (filterContainer && filterContainer.style) {
            if (toggle.checked) {
                filterContainer.style.display = '';
            } else {
                filterContainer.style.display = 'none';
            }
        }
    });
}