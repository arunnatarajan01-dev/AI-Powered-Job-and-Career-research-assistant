(function () {
    const button = document.getElementById("useLocation");
    const input = document.getElementById("location");
    const status = document.getElementById("locationStatus");
    const data = document.getElementById("cityData");
    if (!button || !input || !data) return;

    const cities = JSON.parse(data.textContent);

    function nearest(lat, lng) {
        let best = cities[0];
        let bestDistance = Infinity;
        cities.forEach(function (city) {
            const distance = Math.pow(city.lat - lat, 2) + Math.pow(city.lng - lng, 2);
            if (distance < bestDistance) {
                best = city;
                bestDistance = distance;
            }
        });
        return best.name;
    }

    button.addEventListener("click", function () {
        if (!navigator.geolocation) {
            status.textContent = "This browser cannot read the current location. Type a city instead.";
            return;
        }
        status.textContent = "Reading the current location…";
        navigator.geolocation.getCurrentPosition(
            function (position) {
                const city = nearest(position.coords.latitude, position.coords.longitude);
                input.value = city;
                status.textContent = "Location set to " + city + ".";
            },
            function () {
                status.textContent = "Location permission was denied. Type a city to search.";
            },
            { enableHighAccuracy: false, timeout: 8000 }
        );
    });
})();
