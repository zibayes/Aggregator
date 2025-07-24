document.getElementById('screenshotModeSelect').addEventListener('change', function () {
    const manualControls = document.getElementById('manualScreenshotControls');
    const stagesControls = document.getElementById('stagesControls');
    if (this.value === 'manualScreenshot') {
        manualControls.style.display = 'flex';
        stagesControls.style.display = 'flex';
    } else {
        manualControls.style.display = 'none';
        stagesControls.style.display = 'none';
    }
});

document.getElementById('manualScreenshotControls').addEventListener('change', function (event) {
    const stageSelect = document.getElementById('screenshotStageSelect');

    if (event.target === stageSelect) {
        const selectedStage = stageSelect.value;
        countryControls.style.display = 'none';
        subjectControls.style.display = 'none';
        regionControls.style.display = 'none';

        if (selectedStage === 'russia') {
            countryControls.style.display = 'block';
            subjectControls.style.display = 'block';
        } else if (selectedStage === 'subject') {
            subjectControls.style.display = 'block';
            regionControls.style.display = 'block';
        } else if (selectedStage === 'region') {
            regionControls.style.display = 'block';
        }

        if (window.layers_russia) {
            window.layers_russia.forEach(layer => map.removeLayer(layer));
        }
        if (window.layers_subject) {
            window.layers_subject.forEach(layer => map.removeLayer(layer));
        }
        if (window.labels_regions) {
            window.labels_regions.forEach(layer => map.removeLayer(layer));
        }
        if (window.layers_regions) {
            window.layers_regions.forEach(layer => map.removeLayer(layer));
        }
        if (window.labels_subject) {
            window.labels_subject.forEach(layer => map.removeLayer(layer));
        }

        const mapWidth = document.getElementById('mapWidth').value;
        const mapHeight = document.getElementById('mapHeight').value;
        const mapElement = document.getElementById('map');

        // Элементы для страны
        const countryBorderColor = document.getElementById('countryBorderColor');
        const countryBorderOpacity = document.getElementById('countryBorderOpacity');

        // Элементы для субъекта
        const subjectBorderColor = document.getElementById('subjectBorderColor');
        const subjectBorderOpacity = document.getElementById('subjectBorderOpacity');
        const subjectLabelColor = document.getElementById('subjectLabelColor');
        // const subjectLabelSize = document.getElementById('subjectLabelSize');

        // Элементы для района
        const regionBorderColor = document.getElementById('regionBorderColor');
        const regionBorderOpacity = document.getElementById('regionBorderOpacity');

        if (selectedStage === 'region') {
            result = prtScrRegion(mapElement, window.data, mapWidth, mapHeight, regionBorderColor.value, regionBorderOpacity.value);
            window.layers_regions = result[0];
            borders_bounds = result[1];
            if (borders_bounds.length > 0) {
                allBounds = L.latLngBounds(borders_bounds);
                map.fitBounds(allBounds);
            }
        } else if (selectedStage === 'subject') {
            result = prtScrSubject(mapElement, window.data, mapWidth, mapHeight, regionBorderColor.value, regionBorderOpacity.value, subjectBorderColor.value, subjectBorderOpacity.value, regionLabelColor.value, regionLabelSize.value);
            window.layers_subject = result[0][0];
            borders_bounds = result[0][1];
            window.layers_regions = result[1][0];
            borders_bounds.push(result[1][1]);
            labels_regions = result[1][2];
            if (borders_bounds.length > 0) {
                map.fitBounds(L.latLngBounds(borders_bounds));
            }
        } else if (selectedStage === 'russia') {
            result = prtScrCountry(mapElement, window.data, mapWidth, mapHeight, countryBorderColor.value, countryBorderOpacity.value, subjectBorderColor.value, subjectBorderOpacity.value, subjectLabelColor.value, subjectLabelSize.value);
            window.layers_russia = result[0][0];
            borders_bounds = result[0][1];
            window.layers_subject = result[1][0];
            borders_bounds.push(result[1][1]);
            window.labels_subject = result[1][2];
            if (borders_bounds.length > 0) {
                map.fitBounds(L.latLngBounds(borders_bounds));
            }
        } else if (selectedStage === 'excavation') {
            prtScrExcavation(mapElement, window.data);
        }
    }
});

function updatePolygon() {
    const mapWidth = document.getElementById('mapWidth').value;
    const mapHeight = document.getElementById('mapHeight').value;
    const mapElement = document.getElementById('map');

    // Элементы для страны
    const countryBorderColor = document.getElementById('countryBorderColor');
    const countryBorderOpacity = document.getElementById('countryBorderOpacity');

    // Элементы для субъекта
    const subjectBorderColor = document.getElementById('subjectBorderColor');
    const subjectBorderOpacity = document.getElementById('subjectBorderOpacity');
    const subjectLabelColor = document.getElementById('subjectLabelColor');
    const subjectLabelSize = document.getElementById('subjectLabelSize');

    // Элементы для района
    const regionBorderColor = document.getElementById('regionBorderColor');
    const regionBorderOpacity = document.getElementById('regionBorderOpacity');
    const regionLabelColor = document.getElementById('regionLabelColor');
    const regionLabelSize = document.getElementById('regionLabelSize');

    const stageSelect = document.getElementById('screenshotStageSelect');
    const selectedStage = stageSelect.value;

    if (window.layers_russia) {
        window.layers_russia.forEach(layer => map.removeLayer(layer));
    }
    if (window.layers_subject) {
        window.layers_subject.forEach(layer => map.removeLayer(layer));
    }
    if (window.labels_regions) {
        window.labels_regions.forEach(layer => map.removeLayer(layer));
    }
    if (window.layers_regions) {
        window.layers_regions.forEach(layer => map.removeLayer(layer));
    }
    if (window.labels_subject) {
        window.labels_subject.forEach(layer => map.removeLayer(layer));
    }

    if (selectedStage === 'region') {
        result = prtScrRegion(mapElement, window.data, mapWidth, mapHeight, regionBorderColor.value, regionBorderOpacity.value);
        window.layers_regions = result[0];
    } else if (selectedStage === 'subject') {
        result = prtScrSubject(mapElement, window.data, mapWidth, mapHeight, regionBorderColor.value, regionBorderOpacity.value, subjectBorderColor.value, subjectBorderOpacity.value, regionLabelColor.value, regionLabelSize.value);
        window.layers_subject = result[0][0];
        window.layers_regions = result[1][0];
        window.labels_regions = result[1][2];
    } else if (selectedStage === 'russia') {
        result = prtScrCountry(mapElement, window.data, mapWidth, mapHeight, countryBorderColor.value, countryBorderOpacity.value, subjectBorderColor.value, subjectBorderOpacity.value, subjectLabelColor.value, subjectLabelSize.value);
        window.layers_russia = result[0][0];
        window.layers_subject = result[1][0];
        window.labels_subject = result[1][2];
    } else if (selectedStage === 'excavation') {
        prtScrExcavation(mapElement, window.data);
    }
}

// Функции для обновления параметров
function updateCountryBorderColor(color) {
    updatePolygon();
}

function updateCountryBorderOpacity(opacity) {
    updatePolygon();
}

function updateSubjectBorderColor(color) {
    updatePolygon();
}

function updateSubjectBorderOpacity(opacity) {
    updatePolygon();
}

function updateSubjectLabelColor(color) {
    updatePolygon();
}

function updateSubjectLabelSize(size) {
    updatePolygon();
}

function updateRegionBorderColor(color) {
    updatePolygon();
}

function updateRegionBorderOpacity(opacity) {
    updatePolygon();
}

function updateRegionLabelColor(color) {
    updatePolygon();
}

function updateRegionLabelSize(size) {
    updatePolygon();
}

function updateMapSize() {
    const mapWidth = document.getElementById('mapWidth').value;
    const mapHeight = document.getElementById('mapHeight').value;
    const mapElement = document.getElementById('map');

    if (mapWidth && mapHeight) {
        mapElement.style.width = `${mapWidth}px`;
        mapElement.style.height = `${mapHeight}px`;
        map.invalidateSize();
    }
}