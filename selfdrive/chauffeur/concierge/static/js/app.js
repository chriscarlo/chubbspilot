// app.js - Alpine.js helpers and future code placeholder

// Very small client-side render loop: convert JSON → innerHTML table
document.addEventListener("htmx:afterSwap", e => {
  if (e.detail.target.tagName !== "DIV") return;
  const status = JSON.parse(e.detail.xhr.responseText);
  e.detail.target.innerHTML = `
    <h1 class="text-2xl font-semibold mb-4">Device Status — frame ${status.time}</h1>
    <table class="w-full text-sm">
      <tbody>
        <tr><td class="pr-3">Battery&nbsp;%</td><td>${status.deviceState.batteryPercent}</td></tr>
        <tr><td>Temperature °C</td><td>${status.thermal.cpuTempC}</td></tr>
        <tr><td>Vehicle Speed (m/s)</td><td>${status.carState.vEgo}</td></tr>
      </tbody>
    </table>`;
});