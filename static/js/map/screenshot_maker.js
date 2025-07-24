function displayDataOnMap(polygons, color, fill, opacity, label, label_color = '#000000', label_size = 14) {
    var border_opacity = 1;
    var bounds = [];
    var layers = [];
    var labels = [];
    var last_name = '';

    polygons.forEach(function (feature) {
        if (last_name !== feature.properties.name) {
            if (feature.geometry.coordinates.some(polygon =>
                polygon.some(coord =>
                    coord.some(point => point[0] < -160)
                )
            )) {
                feature.geometry.coordinates = feature.geometry.coordinates.map(polygon =>
                    polygon.map(coord =>
                        coord.map(point => {
                            if (point[0] < -160) {
                                return [point[0] + 360, point[1]];
                            }
                            return point;
                        })
                    )
                );
            }
        }
    });

    polygons.forEach(function (feature) {
        if (last_name !== feature.properties.name) {

            var geojsonLayer = L.geoJSON(feature, {
                style: {
                    color: color,
                    weight: 5,
                    opacity: border_opacity,
                    fill: fill,
                    fillColor: color,
                    fillOpacity: opacity
                }
            }).addTo(map);
            bounds.push(geojsonLayer.getBounds());
            layers.push(geojsonLayer);

            if (label) {
                console.log(feature.properties.name)
                var center = geojsonLayer.getBounds().getCenter();
                label_object = L.marker(center, {
                    icon: L.divIcon({
                        className: 'polygon-label',
                        html: `<span style="color: ${label_color}; font-size: ${label_size}px;">${feature.properties.name}</span>`,
                        iconSize: [170, 40]
                    })
                }).addTo(map);
                labels.push(label_object);
                last_name = feature.properties.name;
            }
        }

    });

    return [layers, bounds, labels];
}

function takeScreenshot() {
    const mapElement = document.getElementById('map');
    const width = mapElement.offsetWidth;
    const height = mapElement.offsetHeight;
    domtoimage.toBlob(mapElement, {width, height})
        .then(function (blob) {
            saveAs(blob, 'map.png');
        })
        .catch(function (error) {
            console.error('Ошибка при создании Blob:', error);
        });
    saveAs(blob, 'map.png');
}

function delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function prtScrCountry(mapElement, data, maxWidth, height, color_country, opacity_country, color_subject, opacity_subject, label_color, label_size, fill_all = true) {
    mapElement.style.maxWidth = maxWidth;
    mapElement.style.height = height;
    map.invalidateSize();
    result1 = displayDataOnMap(data.matching_polygons.Russia, color_country, fill_all, opacity_country, false);
    result2 = displayDataOnMap(data.matching_polygons.Subject, color_subject, true, opacity_subject, true, label_color, label_size);
    return [result1, result2];
}

function prtScrSubject(mapElement, data, maxWidth, height, color_region, opacity_region, color_subject, opacity_subject, label_color, label_size, fill_all = true) {
    mapElement.style.maxWidth = maxWidth;
    mapElement.style.height = height;
    map.invalidateSize();
    result1 = displayDataOnMap(data.matching_polygons.Subject, color_subject, fill_all, opacity_subject, false);
    result2 = displayDataOnMap(data.matching_polygons.Regions, color_region, true, opacity_region, true, label_color, label_size);
    return [result1, result2];
}

function prtScrRegion(mapElement, data, maxWidth, height, color_region, opacity_region, fill_all = true) {
    mapElement.style.maxWidth = maxWidth;
    mapElement.style.height = height;
    map.invalidateSize();
    console.log(data);
    console.log(typeof data);
    result = displayDataOnMap(data.matching_polygons.Regions, color_region, fill_all, opacity_region, false);
    return result;
}

async function prtScrExcavation(mapElement, data) {
    checkbox = document.getElementById('toggleTooltips');
    if (checkbox.checked === false) {
        checkbox.checked = true;
        checkbox.dispatchEvent(new Event('change'));
    }
    checkbox = document.getElementById('toggleLegend');
    if (checkbox.checked === false) {
        checkbox.checked = true;
        checkbox.dispatchEvent(new Event('change'));
    }
    map.fitBounds(bounds);
}

async function showLayers(data) {
    const mapElement = document.getElementById('map');
    result = prtScrCountry(mapElement, data, '1100px', '770px', '#ff0000', 0.3, '#3fb7ed', 0.3, false)
    layers_russia = result[0][0];
    borders_bounds = result[0][1];
    layers_subject = result[1][0];
    borders_bounds.push(result[1][1]);
    labels_subject = result[1][2];
    if (borders_bounds.length > 0) {
        map.fitBounds(L.latLngBounds(borders_bounds));
    }
    setTimeout(function () {
        takeScreenshot();
    }, 2000);
    await delay(2500);
    layers_russia.forEach(function (layer) {
        map.removeLayer(layer);
    });
    layers_subject.forEach(function (layer) {
        map.removeLayer(layer);
    });

    result = prtScrSubject(mapElement, data, '500px', '1150px', '#3fb7ed', 0.3, '#ff0000', 0.3, false)
    layers_subject = result[0][0];
    borders_bounds = result[0][1];
    layers_regions = result[1][0];
    borders_bounds.push(result[1][1]);
    labels_regions = result[1][2]
    if (borders_bounds.length > 0) {
        map.fitBounds(L.latLngBounds(borders_bounds));
    }
    setTimeout(function () {
        takeScreenshot();
    }, 2000);

    await delay(4000);
    labels_subject.forEach(function (layer) {
        map.removeLayer(layer);
    });
    layers_subject.forEach(function (layer) {
        map.removeLayer(layer);
    });
    layers_regions.forEach(function (layer) {
        map.removeLayer(layer);
    });

    result = prtScrRegion(mapElement, data, '1800px', '720px', '#ff0000', 0.3, false)
    layers_regions = result[0];
    borders_bounds = result[1];
    if (borders_bounds.length > 0) {
        allBounds = L.latLngBounds(borders_bounds);
        map.fitBounds(allBounds);
    }
    setTimeout(function () {
        takeScreenshot();
    }, 2500);

    await delay(2500);
    labels_regions.forEach(function (layer) {
        map.removeLayer(layer);
    });
    layers_regions.forEach(function (layer) {
        map.removeLayer(layer);
    });

    prtScrExcavation(mapElement, data)
    setTimeout(function () {
        takeScreenshot();
    }, 2000);
}

document.getElementById('screenshotButton').addEventListener('click', function () {
    const screenshotMode = document.getElementById('screenshotModeSelect').value;
    if (screenshotMode === 'automaticScreenshot') {
        checkbox = document.getElementById('toggleLegend');
        if (checkbox.checked === true) {
            checkbox.checked = false;
            checkbox.dispatchEvent(new Event('change'));
        }
        checkbox = document.getElementById('toggleNorthArrow');
        if (checkbox.checked === false) {
            checkbox.checked = true;
            checkbox.dispatchEvent(new Event('change'));
        }
        checkbox = document.getElementById('toggleGraphicScale');
        if (checkbox.checked === false) {
            checkbox.checked = true;
            checkbox.dispatchEvent(new Event('change'));
        }
        checkbox = document.getElementById('toggleCoordinates');
        if (checkbox.checked === true) {
            checkbox.checked = false;
            checkbox.dispatchEvent(new Event('change'));
        }
        checkbox = document.getElementById('toggleScale');
        if (checkbox.checked === true) {
            checkbox.checked = false;
            checkbox.dispatchEvent(new Event('change'));
        }
        checkbox = document.getElementById('toggleTooltips')
        if (checkbox.checked === true) {
            checkbox.checked = false;
            checkbox.dispatchEvent(new Event('change'));
        }
        showLayers(window.data);
    } else {
        takeScreenshot();
    }
});