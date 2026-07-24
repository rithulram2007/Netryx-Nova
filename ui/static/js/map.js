const NetryxMap = (() => {
  let map = null;
  let markerLayer = null;
  let coverageLayer = null;
  let clusterCircles = [];

  function init(containerId, centerLat = 55.75, centerLon = 37.62, zoom = 5) {
    map = L.map(containerId, {
      center: [centerLat, centerLon],
      zoom: zoom,
      zoomControl: true,
      attributionControl: false,
    });

    L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
      maxZoom: 19,
    }).addTo(map);

    markerLayer = L.layerGroup().addTo(map);
    coverageLayer = L.layerGroup().addTo(map);
    return map;
  }

  function clearMarkers() {
    markerLayer.clearLayers();
    clusterCircles.forEach(c => c.remove());
    clusterCircles = [];
  }

  function addCandidate(lat, lon, inliers, rank, panoid) {
    const color = inliers > 0 ? '#4fc3f7' : '#ef5350';
    const radius = Math.min(Math.max(inliers / 10, 6), 20);
    const circle = L.circleMarker([lat, lon], {
      radius: radius,
      color: color,
      fillColor: color,
      fillOpacity: 0.6,
      weight: 1,
    });
    circle.bindPopup(`<b>#${rank}</b><br>Inliers: ${inliers}<br>Panoid: ${panoid}<br>${lat.toFixed(5)}, ${lon.toFixed(5)}`);
    markerLayer.addLayer(circle);
    return circle;
  }

  function addClusterMarker(lat, lon, score, rank) {
    const color = '#66bb6a';
    const radius = Math.min(score / 5 + 8, 30);
    const circle = L.circleMarker([lat, lon], {
      radius: radius,
      color: color,
      fillColor: color,
      fillOpacity: 0.3,
      weight: 2,
    });
    circle.bindPopup(`<b>Cluster #${rank}</b><br>Score: ${score.toFixed(1)}`);
    markerLayer.addLayer(circle);
    clusterCircles.push(circle);
    return circle;
  }

  function flyTo(lat, lon, zoom) {
    map.flyTo([lat, lon], zoom || 14, { duration: 1 });
  }

  function loadCoverage(geojson) {
    coverageLayer.clearLayers();
    if (!geojson || !geojson.features || geojson.features.length === 0) return;
    L.geoJSON(geojson, {
      pointToLayer: (feature, latlng) => {
        return L.circleMarker(latlng, {
          radius: 2,
          color: '#4fc3f7',
          fillColor: '#4fc3f7',
          fillOpacity: 0.3,
          weight: 0,
        });
      },
    }).addTo(coverageLayer);
  }

  function getCenter() {
    return map.getCenter();
  }

  function getZoom() {
    return map.getZoom();
  }

  return { init, clearMarkers, addCandidate, addClusterMarker, flyTo, loadCoverage, getCenter, getZoom };
})();
