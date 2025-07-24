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
function createMapMarker(point, reportType, reportName, group, point_name) {
    const icon = getGroupIcon(group, reportType);
    const marker = L.marker([point[0], point[1]], {
        color: 'red',
        icon: icon
    }).addTo(map)
        .bindPopup(`<b>${point_name}</b><br><br><i>[${reportType}]</i><br><i>${reportName}</i><br><br>[${group}]<br>${point[0]}, ${point[1]}`)
        .bindTooltip(`<b>${point_name}</b>`, {
            permanent: true,
            direction: 'bottom'
        });

    bounds.extend(marker.getLatLng());
    return marker;
}

// Обработчик изменения состояния точки
function setupPointToggle(markersArray, reportName, group, pointName) {
    document.getElementById(`togglePoints-${reportName}-${group}-${pointName}`)
        .addEventListener('change', function () {
            let array;
            if (`${reportName}` in markersArray) {
                array = markersArray[`${reportName}`];
            } else {
                array = markersArray;
            }
            array.forEach(item => {
                if (item.group.includes(group) && item.point_name === pointName) {
                    this.checked ? item.marker.addTo(map) : map.removeLayer(item.marker);
                }
            });
        });
}

