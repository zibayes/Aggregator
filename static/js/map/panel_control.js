var coordinatesControl = L.control({position: 'bottomright'});
coordinatesControl.onAdd = function (map) {
    var div = L.DomUtil.create('div', 'coordinates');
    div.innerHTML = 'Координаты: '; // Начальное значение
    return div;
};
coordinatesControl.addTo(map);

map.on('mousemove', function (e) {
    coordinatesControl.getContainer().innerHTML = 'Координаты: ' + e.latlng.toString();
});

// L.control.scale().addTo(map);
const graphicScale = L.control.graphicScale({
    showSubunits: true,
    fill: 'fill',
    doubleLine: true,
    position: 'bottomleft'
});
graphicScale.addTo(map);

var northArrowControl = L.control({position: 'topleft'});
northArrowControl.onAdd = function (map) {
    var div = L.DomUtil.create('div', 'north-arrow');
    div.innerHTML = '<img src="/static/img/north_arrow.png" alt="Север" style="width: 40px; height: auto;">';
    return div;
};
northArrowControl.addTo(map);

function centerMap(reportName) {
    const coords = all_markers[reportName];
    if (coords) {
        let bounds = L.latLngBounds();
        Object.keys(coords).forEach(function (point) {
            const marker = coords[point].marker;
            bounds.extend(marker.getLatLng());
        });
        map.fitBounds(bounds);
    }
}


var current_icon;
var markers = [];
var all_markers = {};
var bounds = L.latLngBounds();
var catalogCoords = [];
var all_catalogCoords = {};
var all_catalogPolyline = {};

document.addEventListener('DOMContentLoaded', function () {
    var element = document.querySelector('.leaflet-control-attribution.leaflet-control');
    if (element) {
        element.remove();
    }

    document.getElementById('toggleTooltips').addEventListener('change', function () {
        markers.forEach(function (item) {
            if (this.checked) {
                const popupContent = item.marker.getPopup().getContent();
                const boldTextMatch = popupContent.match(/<b>(.*?)<\/b>/);
                const pointName = boldTextMatch ? boldTextMatch[1] : 'Имя не найдено';
                item.marker.bindTooltip("<b>" + pointName + "</b>", {
                    permanent: true,
                    direction: 'bottom'
                }).openTooltip();
            } else {
                item.marker.unbindTooltip();
            }
        }, this);

        Object.keys(all_markers).forEach(function (reportName) {
            const detached_marker = all_markers[reportName];
            detached_marker.forEach(function (marker) {
                if (marker) {
                    if (this.checked) {
                        const popupContent = marker.marker.getPopup().getContent();
                        const boldTextMatch = popupContent.match(/<b>(.*?)<\/b>/);
                        const pointName = boldTextMatch ? boldTextMatch[1] : 'Имя не найдено';
                        marker.marker.bindTooltip("<b>" + pointName + "</b>", {
                            permanent: true,
                            direction: 'bottom'
                        }).openTooltip();
                    } else {
                        marker.marker.unbindTooltip();
                    }
                }
            }, this);
        }, this);
    });

    document.getElementById('toggleLegend').addEventListener('change', function () {
        if (this.checked) {
            legend.getContainer().style.display = 'block';
        } else {
            legend.getContainer().style.display = 'none';
        }
    });
    document.getElementById('toggleNorthArrow').addEventListener('change', function () {
        if (this.checked) {
            northArrowControl.addTo(map);
        } else {
            map.removeControl(northArrowControl);
        }
    });
    document.getElementById('toggleGraphicScale').addEventListener('change', function () {
        if (this.checked) {
            graphicScale.addTo(map);
        } else {
            map.removeControl(graphicScale);
        }
    });
    document.getElementById('toggleCoordinates').addEventListener('change', function () {
        if (this.checked) {
            coordinatesControl.addTo(map);
        } else {
            map.removeControl(coordinatesControl);
        }
    });
    document.getElementById('toggleScale').addEventListener('change', function () {
        if (this.checked) {
            zoomControl.getContainer().style.display = 'block';
        } else {
            zoomControl.getContainer().style.display = 'none';
        }
    });
});

function syncCheckboxes(reportType) {
    const mainCheckbox = document.getElementById(`toggleMarkerGroup-${reportType}`);
    const nestedCheckboxes = document.querySelectorAll(`.${reportType}_point`);

    nestedCheckboxes.forEach(checkbox => {
        checkbox.checked = mainCheckbox.checked;
        checkbox.dispatchEvent(new Event('change'));
    });
}

function toggleGroup(group) {
    const checkboxes = document.querySelectorAll(`.${group}_point`);
    const groupCheckboxCoords = document.getElementById(`${group}_checkbox`);
    if (groupCheckboxCoords !== null) {
        checkboxes.forEach(checkbox => {
            checkbox.checked = groupCheckboxCoords.checked;
        });
    }
}

function toggleContent(group) {
    const content = document.getElementById(`${group}_content`);
    var toggleIcon = document.getElementById(`${group}_toggle`);
    if (content !== null) {
        if (content.style.display === "none" || content.style.display === "") {
            content.style.display = "block";
            toggleIcon.textContent = "-";
        } else {
            content.style.display = "none";
            toggleIcon.textContent = "+";
        }
    }
}