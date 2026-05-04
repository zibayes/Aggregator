const apiUrl = '/api/get_geojson_polygons/';

function fetchGeoJSON(coordinates) {
    const headers = {"Content-Type": "application/json", "X-CSRFToken": `{{ csrf_token }}`};
    return fetch(apiUrl, {
        method: 'POST',
        headers: headers,
        body: JSON.stringify({points: coordinates})
    })
        .then(response => {
            if (!response.ok) {
                throw new Error('Сеть ответила с ошибкой: ' + response.status);
            }
            return response.json();
        });
}