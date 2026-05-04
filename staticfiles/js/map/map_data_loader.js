// map_data_loader.js
async function loadMapData(url) {
    try {
        showLoadingIndicator(); // опционально
        const response = await fetch(url);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        // Преобразуем ответ в плоский массив для чанковой обработки
        console.log('API response:', data);
        const rawMarkers = [];
        if (window.isAllCoordinates) {
            // data.all_coordinates – объект: { "Акты": { id: { coordinates: {...}, report_name: ... } } }
            for (const [reportType, reports] of Object.entries(data.all_coordinates)) {
                for (const [reportId, reportData] of Object.entries(reports)) {
                    extractMarkersFromReport(
                        rawMarkers,
                        reportType,
                        reportId,
                        reportData.report_name,
                        reportData.coordinates
                    );
                }
            }
        } else {
            // data – один отчёт
            extractMarkersFromReport(
                rawMarkers,
                data.report_type,
                data.report_id,
                data.report_name,
                data.coordinates
            );
        }
        console.log('Extracted markers:', rawMarkers.length);

        // Запускаем создание маркеров чанками
        processMarkersInChunks(rawMarkers);
    } catch (error) {
        console.error('Ошибка загрузки данных карты:', error);
        hideLoadingIndicator();
    }
}

function extractMarkersFromReport(targetArray, reportType, reportId, reportName, coordinates) {
    for (const [group, points] of Object.entries(coordinates)) {
        // Проверяем систему координат (если нужно)
        // if (!points.coordinate_system && reportType !== 'account_card') continue;

        for (const [pointName, coords] of Object.entries(points)) {
            if (pointName === 'coordinate_system' || pointName === 'area') continue;
            if (!Array.isArray(coords) || coords.length !== 2) continue;

            const area = points.area ? parseFloat(String(points.area).replace(',', '.')) : undefined;
            targetArray.push({
                coords: coords,
                reportType: reportType,
                reportName: reportName,
                group: group,
                pointName: pointName,
                area: area,
                reportId: reportId
            });
        }
    }
}

function processMarkersInChunks(rawData, chunkSize = 10, delayMs = 20) {
    let index = 0;
    const total = rawData.length;
    const catalogCoordsMap = {};

    function processNextBatch() {
        // Обрабатываем chunkSize маркеров, но не более оставшихся
        const end = Math.min(index + chunkSize, total);
        for (let i = index; i < end; i++) {
            const item = rawData[i];
            const marker = createMapMarkerFromData(item);

            // Полигоны каталога
            if (item.group.includes('Каталог') || item.reportType === 'commercial_offer') {
                const key = `${item.reportId || item.reportName}-${item.group}`;
                if (!catalogCoordsMap[key]) catalogCoordsMap[key] = [];
                catalogCoordsMap[key].push(item.coords);
            }
        }

        index = end;

        // Обновляем прогресс (можно добавить визуальный индикатор)
        updateLoadingProgress(index, total);

        if (index < total) {
            // Планируем следующую пачку с задержкой
            setTimeout(processNextBatch, delayMs);
        } else {
            // Все готово
            finalizeMapData(catalogCoordsMap);
        }
    }

    // Стартуем
    processNextBatch();
}

// Простейший индикатор (можно улучшить)
function updateLoadingProgress(loaded, total) {
    console.log(`Загружено маркеров: ${loaded} из ${total}`);
}

function finalizeMapData(catalogCoordsMap) {
    // Строим полигоны
    for (const [key, coords] of Object.entries(catalogCoordsMap)) {
        if (coords.length > 2) {
            coords.push(coords[0]); // замыкаем
            const polyline = L.polyline(coords, {color: 'blue'}).addTo(map);
            // Сохраняем для управления видимостью
            if (!window.catalogPolylines) window.catalogPolylines = {};
            window.catalogPolylines[key] = polyline;
        }
    }

    // Подгоняем границы карты
    if (bounds.isValid()) {
        map.fitBounds(bounds);
    }

    hideLoadingIndicator();

    // Включаем чекбоксы легенды, если нужно
}

function createMapMarkerFromData(data) {
    console.log('Creating marker for', data.pointName, data.coords);
    // Эта функция вызывает оригинальную createMapMarker
    const marker = createMapMarker(
        data.coords,
        data.reportType,
        data.reportName,
        data.group,
        data.pointName,
        data.area
    );

    // Добавляем в глобальные массивы для управления видимостью
    markers.push({
        marker: marker,
        group: data.group,
        point_name: data.pointName
    });

    bounds.extend(marker.getLatLng());

    // Настройка переключателя точки в легенде
    setupPointToggle(markers, data.reportName, data.group, data.pointName);

    return marker;
}

function showLoadingIndicator() {
    // Можно показать спиннер или надпись "Загрузка карты..."
}

function hideLoadingIndicator() {
    // Скрыть индикатор
}

// Запускаем загрузку
document.addEventListener('DOMContentLoaded', function () {
    if (window.mapDataUrl) {
        loadMapData(window.mapDataUrl);
    }
});