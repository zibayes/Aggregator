// Универсальная функция для установки обработчика переключения группы
function setupGroupToggle(checkboxId, type, reportName, markersObj, polylineObj = null) {
    const element = document.getElementById(checkboxId);
    if (!element) return;

    element.addEventListener('change', function () {
        // Обновление вложенных маркеров
        updateGroupMarkers(markersObj[reportName], type, this.checked);

        // Обновление дочерних чекбоксов
        updateChildCheckboxes(this, '.single_point');

        // Обработка полигона, если есть
        if (polylineObj) {
            updatePolylineVisibility(`toggleCatalogPolyline-${reportName}`, this.checked, polylineObj[reportName]);
        }
    });
}

// Обновление маркеров группы
function updateGroupMarkers(markers, groupPattern, visible) {
    const patternLower = groupPattern.toLowerCase();
    markers.forEach(item => {
        const isMatch = item.group.includes(groupPattern) ||
            item.group.toLowerCase().includes(patternLower);
        if (isMatch) {
            visible ? item.marker.addTo(map) : map.removeLayer(item.marker);
        }
    });
}

// Обновление видимости полигона (расширенная версия)
function updatePolylineVisibility(checkboxId, visible, polyline) {
    const checkbox = document.getElementById(checkboxId);
    if (checkbox) {
        checkbox.checked = visible;
        checkbox.dispatchEvent(new Event('change'));

        if (polyline) {
            visible ? polyline.addTo(map) : map.removeLayer(polyline);
        }
    }
}

// Основные обработчики
document.getElementById('toggleMarkerGroup-{{ report_name }}').addEventListener('change', function () {
    const reportName = '{{ report_name }}';
    const isChecked = this.checked;

    ['Shurfs', 'Catalog', 'PhotoPoints'].forEach(type => {
        const checkbox = document.getElementById(`toggle${type}-${reportName}`);
        if (checkbox) {
            checkbox.checked = isChecked;
            checkbox.dispatchEvent(new Event('change'));
        }
    });
});
