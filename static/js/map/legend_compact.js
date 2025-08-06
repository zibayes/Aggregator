// Общая функция для обработки переключения группы маркеров
function setupMarkerGroupToggle(options) {
    const {checkboxId, groupPattern, polylineSelector = null} = options;
    let object = document.getElementById(checkboxId)
    if (object) {
        object.addEventListener('change', function () {
            // Обработка маркеров
            markers.forEach(item => {
                if (item.group.includes(groupPattern))
                    this.checked ? item.marker.addTo(map) : map.removeLayer(item.marker);
            });

            // Обновление дочерних чекбоксов
            updateChildCheckboxes(this, '.single_point');

            // Обновление полигона, если указан
            if (polylineSelector) {
                updatePolylineVisibility(polylineSelector, this.checked);
            }
        });
    }
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
function setupPolylineToggle(checkboxId, group) {
    let object = document.getElementById(checkboxId)
    if (object) {
        object.addEventListener('change', function () {
            this.checked ? window.catalogPolyline[group].addTo(map) : map.removeLayer(window.catalogPolyline[group]);
        });
    }
}