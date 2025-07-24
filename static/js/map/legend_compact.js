// Общая функция для обработки переключения группы маркеров
function setupMarkerGroupToggle(options) {
    console.log(options)
    const {checkboxId, groupPattern, polylineSelector = null} = options;
    console.log(checkboxId)
    console.log(document.getElementById(checkboxId))
    document.getElementById(checkboxId).addEventListener('change', function () {
        // Обработка маркеров
        markers.forEach(item => {
            const shouldShow = item.group.includes(groupPattern) && this.checked;
            shouldShow ? item.marker.addTo(map) : map.removeLayer(item.marker);
        });

        // Обновление дочерних чекбоксов
        updateChildCheckboxes(this, '.single_point');

        // Обновление полигона, если указан
        if (polylineSelector) {
            updatePolylineVisibility(polylineSelector, this.checked);
        }
    });
}

// Обновление дочерних чекбоксов
function updateChildCheckboxes(parentCheckbox, selector) {
    const childCheckboxes = parentCheckbox.parentElement.nextElementSibling.querySelectorAll(selector);
    childCheckboxes.forEach(checkbox => {
        checkbox.checked = parentCheckbox.checked;
        checkbox.dispatchEvent(new Event('change'));
    });
}

// Обновление видимости полигона
function updatePolylineVisibility(selector, visible) {
    const polylineCheckbox = document.querySelector(selector);
    if (polylineCheckbox) {
        polylineCheckbox.checked = visible;
        polylineCheckbox.dispatchEvent(new Event('change'));
    }
}

// Настройка переключателя полигона
function setupPolylineToggle(checkboxId, polyline) {
    document.getElementById(checkboxId).addEventListener('change', function () {
        this.checked ? polyline.addTo(map) : map.removeLayer(polyline);
    });
}