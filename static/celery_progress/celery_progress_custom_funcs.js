//  import { defaultMessages, onSuccessCustom, onErrorCustom, onRetryCustom, onIgnoredCustom, onProgressCustom } from './{% static 'celery_progress/celery_progress_custom_funcs.js' %}';

function redirectPost(url, data) {
    var form = document.createElement('form');
    document.body.appendChild(form);
    form.method = 'post';
    form.action = url;
    var input = document.createElement('input');
    input.type = 'hidden';
    input.name = 'acts';
    input.value = data;
    var csrf = document.createElement('input');
    csrf.type = 'hidden';
    csrf.name = 'csrfmiddlewaretoken';
    csrf.value = `{{ csrf_token }}`;
    form.appendChild(input);
    form.appendChild(csrf);
    form.submit();
}

let files_types = {'all': 'Отчёт', 'text': 'Текст', 'images': 'Приложение', 'scan': 'Скан'};
let report_types = {'acts': 'актов', 'scientific_reports': 'научных отчётов', 'open_lists': 'открытых листов'};

function onSuccessCustomRedirect(progressBarElement, progressBarMessageElement, result) {
    if (progressBarElement) {
        progressBarElement.style.backgroundColor = this.barColors.success;
    }
    onSuccessBody(progressBarElement, progressBarMessageElement, result);

    let url = "/deconstructor/";
    setTimeout(() => {
        redirectPost(url, result);
    }, 1000)
}

function onSuccessCustom(progressBarElement, progressBarMessageElement, result) {
    if (progressBarElement) {
        progressBarElement.style.backgroundColor = this.barColors.success;
    }
    onSuccessBody(progressBarElement, progressBarMessageElement, result);
}

function onSuccessBody(progressBarElement, progressBarMessageElement, result) {
    if (progressBarMessageElement) {
        progressBarMessageElement.innerHTML = "Статус: Загрузка <strong>" + report_types[result.file_types] + "</strong> успешно завершена ";
        progressBarMessageElement.nextElementSibling.nextElementSibling.textContent = '';
        progressBarMessageElement.nextElementSibling.hidden = 'hidden';
        let progress_div = progressBarMessageElement.nextElementSibling.nextElementSibling;
        progress_div.nextElementSibling.textContent = 'Время начала обработки: ' + result.time_started;
        if (result.time_ended !== undefined) {
            progress_div.nextElementSibling.nextElementSibling.textContent = 'Время окончания обработки: ' + result.time_ended;
        }
        add_process_status(progressBarMessageElement, result, 'False')
    }
}

function onErrorCustom(progressBarElement, progressBarMessageElement, result_exc) {
    try {
        result_exc = JSON.parse(escapeDoubleQuotes(result_exc).replace(/'/g, '"'));
    } finally {
        progressBarElement.style.backgroundColor = this.barColors.error;
        progressBarMessageElement.textContent = "Ошибка обработки задачи: " + result_exc;
    }
    result = result_exc.progress_json;
    progressBarElement.style.backgroundColor = this.barColors.error;
    progressBarMessageElement.innerHTML = "Статус: Ошибка загрузки <strong>" + report_types[result.file_types] + "</strong> ";
    progressBarMessageElement.nextElementSibling.textContent = result_exc.error_text;
    let progress_div = progressBarMessageElement.nextElementSibling.nextElementSibling;
    progress_div.nextElementSibling.textContent = 'Время начала обработки: ' + result.time_started;
    if (result.time_ended !== undefined) {
        progress_div.nextElementSibling.nextElementSibling.textContent = 'Время окончания обработки: ' + result.time_ended;
    }
    add_process_status(progressBarMessageElement, result, 'True')
}

function onTaskErrorCustom(progressBarElement, progressBarMessageElement, result) {
    this.onError(progressBarElement, progressBarMessageElement, result);
}

function escapeDoubleQuotes(str) {
    return str.replace(/"/g, '\\"');
}

function onResultCustom(resultElement, result) {
    try {
        result = JSON.parse(escapeDoubleQuotes(result).replace(/'/g, '"'));
        if (resultElement) {
            // resultElement.textContent = result.error_text;
        }
    } finally {
        this.onRetry()
    }
}

function onRetryCustom(progressBarElement, progressBarMessageElement, excMessage, retrySeconds) {
    let message = 'Статус: Повторная попытка подключения через ' + retrySeconds + ' секунд: ' + excMessage;
    progressBarElement.style.backgroundColor = this.barColors.error;
    progressBarMessageElement.textContent = message;
}

function onIgnoredCustom(progressBarElement, progressBarMessageElement, result) {
    progressBarElement.style.backgroundColor = this.barColors.ignored;
    progressBarMessageElement.textContent = result || 'Статус: Результат загрузки проигнорирован';
}

function onProgressCustom(progressBarElement, progressBarMessageElement, progress) {
    progressBarElement.style.backgroundColor = this.barColors.progress;
    progressBarElement.style.width = progress.percent + "%";
    var description = progress.description || "";
    if (progress.current == 0) {
        if (progress.pending === true) {
            progressBarMessageElement.textContent = this.messages.waiting;
        } else {
            progressBarMessageElement.textContent = this.messages.started;
        }
    } else {
        if (description !== '') {
            progressBarMessageElement.innerHTML = 'Статус: Идёт загрузка и обработка <strong>' +
                report_types[description.file_types] + '</strong>';
            let expected_time = ''
            if (description.expected_time !== undefined) {
                expected_time = 'Ожидаемое время выполнения: ' + description.expected_time
            }
            let progress_div = progressBarMessageElement.nextElementSibling.nextElementSibling;
            progress_div.textContent = "Прогресс: Всего обработано " +
                progress.current + '/' + progress.total + ' страниц (' + progress.percent + "%" + ') ' + expected_time;
            progress_div.nextElementSibling.textContent = 'Время начала обработки: ' + description.time_started;
            if (description.time_ended !== undefined) {
                progress_div.nextElementSibling.nextElementSibling.textContent = 'Время окончания обработки: ' + description.time_ended + expected_time;
            }
            add_process_status(progressBarMessageElement, description, 'False')
        }
    }
}

function add_process_status(progressBarMessageElement, result, isError) {
    if (result !== '') {
        let ul = document.createElement('ul');
        let files_div = progressBarMessageElement.nextElementSibling.nextElementSibling.nextElementSibling.nextElementSibling.nextElementSibling;
        files_div.innerHTML = ``
        files_div.appendChild(ul)
        for (const [key, value] of Object.entries(result.file_groups)) {
            let li = document.createElement('li');
            ul.appendChild(li);
            let file = document.createElement('a');
            file.textContent = 'Составной отчёт';
            li.appendChild(file);
            if (result.file_types !== 'open_lists') {
                if (value.length > 1) {
                    let sub_ul = document.createElement('ul');
                    li.appendChild(sub_ul)
                    for (let i = 0; i < value.length; i++) {
                        let sub_li = document.createElement('li');
                        sub_ul.appendChild(sub_li)
                        let sub_file = document.createElement('a');
                        add_process_icon(sub_file, sub_li, value[i], result, key, isError);
                    }
                } else {
                    add_process_icon(file, li, value[0], result, key, isError);
                }
            } else {
                add_process_icon(file, li, value, result, key, isError);
            }

        }
    }
}

function add_process_icon(file, li, value, result, key, isError) {
    let br = document.createElement('br');
    let origin = document.createElement('a');
    origin.textContent = value.origin_name;
    li.appendChild(origin);
    li.appendChild(br);
    file.href = `/${result.file_types}/${key}`;
    file.className = 'link'
    let file_text;
    if (result.file_types !== 'open_lists') {
        file_text = files_types[value.type];
    } else {
        file_text = 'Открытый лист';
    }
    file.textContent = file_text;
    li.appendChild(file);
    checkURL(file);
    let deter = document.createElement('a');
    deter.textContent = '/';
    li.appendChild(deter);
    let file_formalized = document.createElement('a');
    file_formalized.textContent = 'Исходник';
    file_formalized.href = '/' + value.path;
    file_formalized.className = 'link'
    li.appendChild(file_formalized);
    checkURL(file_formalized);

    let icon = document.createElement('a');
    let text_content = ` (${value.pages.processed}/${value.pages.all})`;
    if (value.processed === 'True') {
        icon.textContent = text_content + ` ✅`;
    } else if (value.processed === 'False') {
        if (isError === 'True') {
            icon.textContent = text_content + ` ❌`;
        } else {
            icon.textContent = text_content;
        }
    } else if (value.processed === 'Processing') {
        if (isError === 'True') {
            icon.textContent = text_content + ` ❌`;
        } else {
            icon.textContent = text_content + ` ⏳`;
        }
    }
    li.appendChild(icon)
}

async function checkURL(link) {
    try {
        const response = await fetch(link.href, {method: 'HEAD'});
        if (response.ok) {
            // console.log(`URL доступен: ${link.href}`);
        } else {
            link.removeAttribute('href');
            link.style.color = 'gray';
            link.textContent += ' (Файл удалён)'
        }
    } catch (error) {
        link.removeAttribute('href');
        link.style.color = 'gray';
        link.textContent += ' (Файл удалён)'
    }
}