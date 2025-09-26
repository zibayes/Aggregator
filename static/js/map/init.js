let groupCheckbox;
// Инициализация карты
var map = L.map('map').setView([56.01528, 92.89325], 10);  // , {crs: L.CRS.EPSG3395}
var maxZoom = 20;
var zoomControl = map.zoomControl;
var current_icon;
var markers = [];
var all_markers = {};
var bounds = L.latLngBounds();
var catalogCoords = [];
var all_catalogCoords = {};
window.all_catalogPolyline = {};
window.catalogPolyline = {};

document.addEventListener('DOMContentLoaded', function () {
    const allContents = document.querySelectorAll('[id$="_content"]');
    allContents.forEach(content => content.style.display = 'none');
    window.labels_regions = undefined;
    window.labels_subject = undefined;
    window.layers_regions = undefined;
    window.layers_russia = undefined;
    window.layers_subject = undefined;
    /*
    fetchGeoJSON(coordinatesJson)
        .then(received_data => {
            if (received_data && received_data.matching_polygons) {
                window.data = received_data;
                console.log(window.data)
            } else {
                console.log('Нет данных для отображения');
            }
        })
        .catch(error => {
            console.error('Произошла ошибка при получении данных:', error);
        });
     */
});