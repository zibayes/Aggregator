// Выносим определение иконки в отдельную функцию
function getGroupIcon(group, reportType) {
    // Проверяем каждый тип группы в порядке приоритета
    if (group.includes('Каталог') || reportType === 'commercial_offer') {
        return catalog_icons;
    }

    if (group.includes('Шурфы')) {
        return pits_icons;
    }

    if (group.includes('фото')) {
        return photos_icons;
    }

    if (group.includes('Центр') || reportType === 'geo_object') {
        return center_icons;
    }

    // Возвращаем иконку по умолчанию
    return center_icons;
}

// Универсальная функция создания маркера
function createMapMarker(point, reportType, reportName, group, point_name, area = undefined) {
    const icon = getGroupIcon(group, reportType);
    let popup = `<b>${point_name}</b><br><br><i>[${reportType}]</i><br><i>${reportName}</i><br><br>[${group}]<br>${point[0]}, ${point[1]}`;

    if (area !== undefined){
        popup += `<br><br>[Площадь полигона]<br>${area.toFixed(2)} м²`;
    }

    const marker = L.marker([point[0], point[1]], {
        color: 'red',
        icon: icon
    }).bindPopup(popup)
        .bindTooltip(`<b>${point_name}</b>`, {
            permanent: true,
            direction: 'bottom'
        });

    markerClusterGroup.addLayer(marker);

    bounds.extend(marker.getLatLng());
    return marker;
}

// Обработчик изменения состояния точки
function setupPointToggle(markersArray, reportName, group, pointName) {
    let object = document.getElementById(`togglePoints-${reportName}-${group}-${pointName}`);
    object.addEventListener('change', function () {
        let array;
        if (`${reportName}` in markersArray) {
            array = markersArray[`${reportName}`];
        } else {
            array = markersArray;
        }
        array.forEach(item => {
            if (item.group.includes(group) && item.point_name === pointName) {
                this.checked ? markerClusterGroup.addLayer(item.marker) : markerClusterGroup.removeLayer(item.marker);
            }
        });
    });
}

// Функция для создания переключаемого элемента с сохранением оригинальных ID
function createToggleItem(idPrefix, label, iconColor, report_name, report_type, group, checked = true, indent = 0) {
    const idMap = {
        'shurfs': 'toggleShurfs',
        'catalog': 'toggleCatalog',
        'photos': 'togglePhotoPoints',
        'center': 'toggleCenterPoints'
    };
    const toggleId = idMap[idPrefix] || `toggle${idPrefix.charAt(0).toUpperCase() + idPrefix.slice(1)}`;

    return `
<div style="margin-left: ${indent}px;">
    <span style="cursor: pointer;" id="${idPrefix}-${report_name}-${group}_toggle" class="toggle-icon" onclick="toggleContent('${idPrefix}-${report_name}-${group}')">+</span>
    <input type="checkbox" id="${toggleId}-${report_name}-${group}" class="${report_type}_point" style="margin-right: 3px;" ${checked ? 'checked' : ''}>
    <i style="background: ${iconColor};"></i> ${label}
</div>
<div id="${idPrefix}-${report_name}-${group}_content" style="margin-left: ${indent + 20}px; display: none;">
`;
}

// Функция для чекбоксов с кастомными ID (если нужно)
function createCheckboxItem(id, label, checked = true, indent = 20, className = 'single_point') {
    return `
<div style="margin-left: ${indent}px;">
    <input type="checkbox" id="${id}" class="${className}" style="margin-right: 3px;" ${checked ? 'checked' : ''}>
    ${label}
</div>
`;
}

// Функция для разделов с сохранением ID
function createReportSection(id, label, report_type, isChecked = true, hasCenterButton = false, reportName = '') {
    return `
<div style="cursor: pointer; margin-left: 20px;">
    <span id="${id}_toggle" class="toggle-icon" onclick="toggleContent('${id}')">+</span>
    <input type="checkbox" id="${id.startsWith('report-') ? 'toggleMarkerGroup-' + id.replace('report-', '') : id}"
           class="${report_type}_point" style="margin-right: 3px;"
           ${isChecked ? 'checked' : ''}
           ${`onchange="syncCheckboxes('${report_type}', '${id.startsWith('report-') ? 'toggleMarkerGroup-' + id.replace('report-', '') : id}')"`}>
    ${label}
    ${hasCenterButton ? `<button class="center-button" title="Центрировать карту на этом отчете" style="margin-left: 5px; cursor: pointer;" onclick="centerMap('${reportName}')">➔</button>` : ''}
</div>
<div id="${id}_content" style="margin-left: 40px; display: none;">
`;
}