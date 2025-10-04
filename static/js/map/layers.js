function TileXYToQuadKey(tileX, tileY, levelOfDetail) {
    var quadKey = '';
    for (var i = levelOfDetail; i > 0; i--) {
        var digit = '0';
        var mask = 1 << (i - 1);
        if ((tileX & mask) != 0) {
            digit++;
        }
        if ((tileY & mask) != 0) {
            digit++;
            digit++;
        }
        quadKey += digit;
    }
    return quadKey;
}

L.TileLayer.Bing = L.TileLayer.extend({
    getTileUrl: function (coords) {
        var quadKey = TileXYToQuadKey(coords.x, coords.y, coords.z);
        return 'http://ecn.t0.tiles.virtualearth.net/tiles/r' + quadKey + '.jpeg?g=1180&mkt=en-us&lbl=l1&stl=h&shading=hill&n=z';
    },
    getAttribution: function () {
        return "<a href='https://www.bing.com/maps'>Bing Maps</a>";
    }
});

L.tileLayer.bing = function () {
    return new L.TileLayer.Bing();
};

L.TileLayer.BingSattelite = L.TileLayer.extend({
    getTileUrl: function (coords) {
        var quadKey = TileXYToQuadKey(coords.x, coords.y, coords.z);
        return 'http://ecn.t0.tiles.virtualearth.net/tiles/a' + quadKey + '.jpeg?g=1180&mkt=en-us&lbl=l1&stl=h&shading=hill&n=z';
    },
    getAttribution: function () {
        return "<a href='https://www.bing.com/maps'>Bing Maps</a>";
    }
});

L.tileLayer.bingSattelite = function () {
    return new L.TileLayer.BingSattelite();
};

L.TileLayer.BingRoadsEn = L.TileLayer.extend({
    getTileUrl: function (coords) {
        var quadKey = TileXYToQuadKey(coords.x, coords.y, coords.z);
        return 'http://ecn.t0.tiles.virtualearth.net/tiles/r' + quadKey + '.jpeg?g=1180&mkt=en-us&it=G,VE,BX,L,LA&shading=hill';
    },
    getAttribution: function () {
        return "<a href='https://www.bing.com/maps'>Bing Maps - Roads</a>";
    }
});

L.tileLayer.bingRoadsEn = function () {
    return new L.TileLayer.BingRoadsEn();
};

L.TileLayer.BingRoadsRu = L.TileLayer.extend({
    getTileUrl: function (coords) {
        var quadKey = TileXYToQuadKey(coords.x, coords.y, coords.z);
        return 'http://ecn.t0.tiles.virtualearth.net/tiles/r' + quadKey + '.jpeg?g=1180&mkt=ru-RU&it=G,VE,BX,L,LA&shading=hill';
    },
    getAttribution: function () {
        return "<a href='https://www.bing.com/maps'>Bing Maps - Roads (ru)</a>";
    }
});

L.tileLayer.bingRoadsRu = function () {
    return new L.TileLayer.BingRoadsRu();
};

function getRandomSubdomain() {
    const subdomains = ['t0', 't1', 't2', 't3']; // Поддомены Bing Maps
    return subdomains[Math.floor(Math.random() * subdomains.length)];
}

L.TileLayer.BingHybrid = L.TileLayer.extend({
    getTileUrl: function (coords) {
        var quadKey = TileXYToQuadKey(coords.x, coords.y, coords.z);
        var subdomain = getRandomSubdomain();
        return 'http://ak.dynamic.' + subdomain + '.tiles.virtualearth.net/comp/ch/' + quadKey + '.jpeg?g=1180&mkt=ru-RU&it=A,G,L&shading=hill&og=8&n=z';
    },
    getAttribution: function () {
        return "<a href='https://www.bing.com/maps'>Bing Maps - Hybrid</a>";
    }
});

L.tileLayer.bingHybrid = function () {
    return new L.TileLayer.BingHybrid();
};

function latLngToTile(lat, lng, zoom) {
    var x = Math.floor((lng + 180) / 360 * Math.pow(2, zoom));
    var y = Math.floor((1 - Math.log(Math.tan(lat * Math.PI / 180) + 1 / Math.cos(lat * Math.PI / 180)) / Math.PI) / 2 * Math.pow(2, zoom));
    return [x, y];
}

function tileToLatLng(x, y, zoom) {
    const n = Math.pow(2, zoom);
    const lon_deg = x / n * 360.0 - 180.0;
    const lat_rad = Math.atan(Math.sinh(Math.PI * (1 - 2 * y / n)));
    const lat_deg = lat_rad * (180.0 / Math.PI);

    return {lat: lat_deg, lng: lon_deg};
}

proj4.defs("EPSG:3395", "+proj=merc +lon_0=0 +k=1 +x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs +type=crs");
proj4.defs("EPSG:3785", "+proj=merc +a=6378137 +b=6378137 +lat_ts=0 +lon_0=0 +x_0=0 +y_0=0 +k=1 +units=m +nadgrids=@null +wktext +no_defs +type=crs");

L.TileLayer.Yandex = L.TileLayer.extend({
    getTileUrl: function (coords) {
        // var latLng = crs.projection.unproject([coords.x, coords.y]);
        var latLng = tileToLatLng(coords.x, coords.y, coords.z);

        // Преобразование географических координат в нужную проекцию
        var point = proj4('EPSG:3395', 'EPSG:3785', [latLng.lng, latLng.lat]);

        var tilePoint = latLngToTile(point[1], point[0], coords.z);

        return 'https://core-renderer-tiles.maps.yandex.net/tiles?l=map&x=' + tilePoint[0] + '&y=' + tilePoint[1] + '&z=' + coords.z + '&scale=2';
    },
    getAttribution: function () {
        return '<a href="https://yandex.ru" target="_blank">Яндекс</a>';
    }
});

L.tileLayer.yandex = function () {
    return new L.TileLayer.Yandex();
};

var baseLayers = {
    'OpenStreetMap': L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '<a href="https://www.openstreetmap.org/copyright" target="_blank">OpenStreetMap</a> contributors'
    }),

    'Google': L.tileLayer('https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
        attribution: '<a href="https://google.com" target="_blank">Google</a>'
    }),

    'Google satellite': L.tileLayer('https://{s}.google.com/vt/lyrs=s&x={x}&y={y}&z={z}', {
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
        attribution: '<a href="https://google.com" target="_blank">Google</a>'
    }),

    'Google hybrid': L.tileLayer('https://{s}.google.com/vt/lyrs=y&x={x}&y={y}&z={z}', {
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
        attribution: '<a href="https://google.com" target="_blank">Google</a>'
    }),

    'Google Roads': new L.LayerGroup([
        L.tileLayer('https://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
            subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
            attribution: '<a href="https://google.com" target="_blank">Google</a>'
        }),
        L.tileLayer('http://{s}.google.com/vt/lyrs=h&x={x}&y={y}&z={z}', {
            subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
            attribution: '<a href="https://google.com" target="_blank">Google</a>'
        }),
    ]),
    'Google Streets': L.tileLayer('http://{s}.google.com/vt/lyrs=m&x={x}&y={y}&z={z}', {
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
        attribution: '<a href="https://google.com" target="_blank">Google</a>'
    }),

    'Google Streets Alternative': L.tileLayer('http://{s}.google.com/vt/lyrs=r&x={x}&y={y}&z={z}', {
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
        attribution: '<a href="https://google.com" target="_blank">Google</a>'
    }),

    'Google Terrain': L.tileLayer('http://{s}.google.com/vt/lyrs=p&x={x}&y={y}&z={z}', {
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
        attribution: '<a href="https://google.com" target="_blank">Google</a>'
    }),

    'Google Terrain Alternative': L.tileLayer('http://{s}.google.com/vt/lyrs=t&x={x}&y={y}&z={z}', {
        subdomains: ['mt0', 'mt1', 'mt2', 'mt3'],
        attribution: '<a href="https://google.com" target="_blank">Google</a>'
    }),

    'Yandex1': L.tileLayer('https://core-renderer-tiles.maps.yandex.net/tiles?l=map&x={x}&y={y}&z={z}&scale=2', {
        attribution: '<a href="https://yandex.ru" target="_blank">Yandex</a>',
    }),

    'Yandex satellite': L.tileLayer('https://core-sat.maps.yandex.net/tiles?l=sat&x={x}&y={y}&z={z}&scale=1', {
        attribution: '<a href="https://yandex.ru" target="_blank">Yandex</a>',
    }),

    'Yandex hybrid': new L.LayerGroup([
        L.tileLayer('https://core-sat.maps.yandex.net/tiles?l=sat&x={x}&y={y}&z={z}&scale=1'),
        L.tileLayer('https://core-renderer-tiles.maps.yandex.net/tiles?l=skl&x={x}&y={y}&z={z}&scale=1'),
    ]),

    '2GIS': L.tileLayer('https://{s}.maps.2gis.com/tiles?x={x}&y={y}&z={z}&v=1', {
        subdomains: ['tile1', 'tile2', 'tile3'],
        attribution: '<a href="https://2gis.com" target="_blank">2GIS </a>'
    }),

    'Bing Maps': L.tileLayer.bing(),
    'Bing Satellite': L.tileLayer.bingSattelite(),
    'Bing Roads (en)': L.tileLayer.bingRoadsEn(),
    'Bing Roads (ru)': L.tileLayer.bingRoadsRu(),
    'Bing Hybrid': L.tileLayer.bingHybrid(),
    'Yandex': L.tileLayer.yandex(),

    "ArcGIS Hybrid": new L.LayerGroup([
        L.tileLayer('https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: maxZoom,
            attribution: 'ArcGIS.Imagery'
        }),
        L.tileLayer('https://server.arcgisonline.com/arcgis/rest/services/Reference/World_Boundaries_and_Places/MapServer/tile/{z}/{y}/{x}', {
            maxZoom: maxZoom,
            attribution: 'ArcGIS online Hybrid'
        })
    ]),

    "ArcGIS Imagery": L.tileLayer('https://server.arcgisonline.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: maxZoom,
        attribution: 'ArcGIS.Imagery'
    }),

    "ArcGIS Streets": L.tileLayer('https://server.arcgisonline.com/arcgis/rest/services/World_Street_Map/MapServer/tile/{z}/{y}/{x}', {
        maxZoom: maxZoom,
        attribution: 'ArcGIS.Streets'
    }),

    'My Raster Tiles': L.tileLayer('http://localhost:8090/raster/ThunderforestOSM/{z}/{x}/{y}.png', {
        attribution: 'Мои растровые тайлы',
        maxZoom: 15,
        minZoom: 7,
        errorTileUrl: '',
        crossOrigin: true,
        tms: true
    }),

    'My Vector Tiles': L.vectorGrid.protobuf('http://localhost:8090/vector/data/maptiler-contours/{z}/{x}/{y}.pbf', {
        vectorTileLayerStyles: {
            'contour': {
                // Стилизация по значимости линий (атрибут nth_line)
                style: function(feature) {
                    var nth_line = feature.properties.nth_line;
                    if (nth_line === 10) {
                        return {
                            weight: 2.5,
                            color: '#000000',
                            opacity: 1
                        };
                    } else if (nth_line === 5) {
                        return {
                            weight: 2,
                            color: '#666666',
                            opacity: 0.8
                        };
                    } else if (nth_line === 2) {
                        return {
                            weight: 1.5,
                            color: '#999999',
                            opacity: 0.7
                        };
                    } else {
                        return {
                            weight: 1,
                            color: '#cccccc',
                            opacity: 0.5
                        };
                    }
                }
            }
        },
        interactive: true,
        minZoom: 9,  // Важно! Минимальный зум 9, как указано в метаданных
        maxZoom: 14, // Максимальный зум 14
        attribution: '<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap contributors</a>'
    }),
};

var additionalLayers = {
    'Cadastre site': L.tileLayer.wms('https://nspd.gov.ru/api/aeggis/v4/36048/wms?', {
        version: '1.3.0',
        format: 'image/png',
        layers: '36048',
        transparent: true,
        attribution: '<a href="https://nspd.gov.ru" target="_blank">НСПД</a> contributors'
    }),

    'Cadastre quarter': L.tileLayer.wms('https://nspd.gov.ru/api/aeggis/v4/36071/wms?', {
        version: '1.3.0',
        format: 'image/png',
        layers: '36071',
        transparent: true,
        attribution: '<a href="https://nspd.gov.ru" target="_blank">НСПД</a> contributors'
    }),

    'Cadastre district': L.tileLayer.wms('https://nspd.gov.ru/api/aeggis/v4/36070/wms?', {
        version: '1.3.0',
        format: 'image/png',
        layers: '36070',
        transparent: true,
        attribution: '<a href="https://nspd.gov.ru" target="_blank">НСПД</a> contributors'
    }),

    'Cadastre county': L.tileLayer.wms('https://nspd.gov.ru/api/aeggis/v4/36945/wms?', {
        version: '1.3.0',
        format: 'image/png',
        layers: '36945',
        transparent: true,
        attribution: '<a href="https://nspd.gov.ru" target="_blank">НСПД</a> contributors'
    }),

    'Height Contours': L.vectorGrid.protobuf('http://localhost:8090/vector/data/maptiler-contours/{z}/{x}/{y}.pbf', {
        vectorTileLayerStyles: {
            'contour': {
                style: function(feature) {
                    var nth_line = feature.properties.nth_line;
                    if (nth_line === 10) {
                        return {weight: 2.5, color: '#000000', opacity: 1};
                    } else if (nth_line === 5) {
                        return {weight: 2, color: '#666666', opacity: 0.8};
                    } else if (nth_line === 2) {
                        return {weight: 1.5, color: '#999999', opacity: 0.7};
                    } else {
                        return {weight: 1, color: '#cccccc', opacity: 0.5};
                    }
                }
            }
        },
        interactive: true,
        minZoom: 9,
        maxZoom: 14,
        attribution: '<a href="https://www.maptiler.com/copyright/" target="_blank">&copy; MapTiler</a> <a href="https://www.openstreetmap.org/copyright" target="_blank">&copy; OpenStreetMap contributors</a>'
    })
}

baseLayers["OpenStreetMap"].addTo(map);

function additionalLayerSwitch() {
    var additionalSelectedLayer = document.getElementById('additionalLayerSelect').value;
    for (layer in additionalLayers) {
        map.removeLayer(additionalLayers[layer]);
    }
    if (additionalSelectedLayer !== 'No additional layer') {
        additionalLayers[additionalSelectedLayer].addTo(map);
    }
}

document.getElementById('baseLayerSelect').addEventListener('change', function () {
    var selectedLayer = this.value;
    for (var layer in baseLayers) {
        map.removeLayer(baseLayers[layer]);
    }
    baseLayers[selectedLayer].addTo(map);

    additionalLayerSwitch();
});

document.getElementById('additionalLayerSelect').addEventListener('change', function () {
    additionalLayerSwitch();
});