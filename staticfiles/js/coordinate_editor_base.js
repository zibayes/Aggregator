function removeInput(button) {
    var inputGroup = button.parentElement;
    inputGroup.parentElement.removeChild(inputGroup);
}

let counter = 0;

function addPoint(group) {
    counter += 1;
    var inputGroup = document.createElement('div');
    inputGroup.className = 'input-group mb-3';
    inputGroup.innerHTML = `
        <input type="text" name="point[{{ group }}-new${counter}]" class="form-control" placeholder="Введите координаты такого формата: [Название точки]: [x]; [y]">
        <button type="button" class="btn btn-danger" onclick="removeInput(this)">Удалить</button>
    `;
    document.getElementById('points-' + group).appendChild(inputGroup);
}

function removePolygon(group) {
    var polygon = document.getElementById('polygon-' + group);
    polygon.parentElement.removeChild(polygon);
}