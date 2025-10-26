let trendChartInstance = null;

// Color map for badges and chart bars
const colorMap = {
  "Low": "green",
  "Medium": "orange",
  "High": "red"
};

const mappingValue = {"Low": 0, "Medium": 1, "High": 2};

// populate locations dropdown and set up event handlers
window.onload = async function() {
  // populate locations
  try {
    const res = await fetch("/locations");
    const locs = await res.json();
    const locationSelect = document.getElementById("location");
    locationSelect.innerHTML = "";
    if (locs.length === 0) {
      const opt = document.createElement("option");
      opt.value = "";
      opt.textContent = "No locations found in dataset";
      locationSelect.appendChild(opt);
    } else {
      locs.forEach(l => {
        const opt = document.createElement("option");
        opt.value = l;
        opt.textContent = l;
        locationSelect.appendChild(opt);
      });
    }

    // After locations loaded, fetch Compare + Live data
    fetchCompareAndLive(locs);

  } catch (err) {
    console.error("Failed to load locations", err);
  }

  // Scroll to a target section if server suggested one
  if (typeof targetSection !== "undefined" && targetSection) {
    const el = document.getElementById(targetSection);
    if (el) el.scrollIntoView({ behavior: "smooth" });
  }

  // attach form handler
  document.getElementById("predictBtn").addEventListener("click", handlePredict);
  document.getElementById("trendButton").addEventListener("click", () => {
    const data = gatherFormData();
    if (data) fetchTrend(data);
  });

  // set initial live time
  document.getElementById("liveTime").innerText = new Date().toLocaleTimeString();
};

// -----------------------
// Gather form data for prediction/trend
// -----------------------
function gatherFormData(){
  const date = document.getElementById("date").value;
  const hour = document.getElementById("hour").value;
  const location = document.getElementById("location").value;

  if (!date || !hour || !location) {
    alert("Please fill all inputs (Date, Hour, Location).");
    return null;
  }

  const weekdayNames = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];
  const dayIndex = new Date(date).getDay();
  const day_of_week = weekdayNames[dayIndex];

  return {
    date,
    day_of_week,
    hour,
    location
  };
}

// -----------------------
// Handle single prediction
// -----------------------
async function handlePredict(e){
  e.preventDefault();
  const data = gatherFormData();
  if (!data) return;

  try {
    const res = await fetch("/api/predict", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(data)
    });
    const result = await res.json();
    if (result.error) {
      alert("Error: " + result.error);
      return;
    }

    // show results
    document.getElementById("result").style.display = "block";
    const badge = document.getElementById("congestion");
    badge.innerText = result.congestion;
    badge.style.background = colorMap[result.congestion] || "gray";
    badge.style.color = "white";
    badge.style.padding = "6px 8px";
    badge.style.borderRadius = "6px";

    data.traffic_volume = parseFloat(result.volume.replace(/[^\d.]/g, ''));
    data.average_speed_kmph = parseFloat(result.speed.replace(/[^\d.]/g, ''));
    data.occupancy_ratio = parseFloat(result.occupancy.replace(/[^\d.]/g, '')) / 100;

    // draw weekly trend automatically
    fetchTrend(data);

  } catch (err) {
    console.error(err);
    alert("Prediction failed: " + err.message);
  }
}

// -----------------------
// Weekly Trend Chart
// -----------------------
async function fetchTrend(formData) {
  if (!formData) return;
  try {
    const res = await fetch("/api/trend", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(formData)
    });
    const trendArr = await res.json();
    if (trendArr.error) {
      alert("Trend error: " + trendArr.error);
      return;
    }

    const labels = trendArr.map(d => d.day);
    const values = trendArr.map(d => d.congestion_value);
    const colors = trendArr.map(d => colorMap[d.congestion] || "gray");

    const ctx = document.getElementById("trendChart").getContext("2d");
    if (trendChartInstance) trendChartInstance.destroy();

    trendChartInstance = new Chart(ctx, {
      type: 'bar',
      data: {
        labels: labels,
        datasets: [{
          label: "Congestion (0=Low,1=Medium,2=High)",
          data: values,
          backgroundColor: colors,
          borderRadius: 6
        }]
      },
      options: {
        responsive: true,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: function(context) {
                const idx = context.dataIndex;
                return `${trendArr[idx].congestion} (${values[idx]})`;
              }
            }
          }
        },
        scales: {
          y: {
            min: 0,
            max: 2,
            ticks: {
              stepSize: 1,
              callback: function(v) {
                if (v === 0) return 'Low';
                if (v === 1) return 'Medium';
                if (v === 2) return 'High';
                return v;
              }
            }
          }
        }
      }
    });

  } catch (err) {
    console.error("Trend fetch failed:", err);
  }
}

// -----------------------
// Dynamic Compare + Live Data for ALL locations
// -----------------------
async function fetchCompareAndLive(allLocations) {
  try {
    const locations = allLocations || [];
    if (!locations || locations.length === 0) return;

    const hour = new Date().getHours();
    const date = new Date().toISOString().split('T')[0];

    const compareContainer = document.getElementById("compareResults");
    const liveContainer = document.getElementById("liveResults");

    compareContainer.innerHTML = "";
    liveContainer.innerHTML = "";

    for (let loc of locations) {
      const payload = { location: loc, hour: hour, date: date };
      const res = await fetch("/api/trend", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload)
      });
      const data = await res.json();
      if (data.error) continue;

      const today = data[0]; // first day
      let emoji = "🟢";
      if(today.congestion.toLowerCase() === "medium") emoji = "🟡";
      if(today.congestion.toLowerCase() === "high") emoji = "🔴";

      // Compare
      compareContainer.innerHTML += `<h3>${loc}: ${today.congestion} ${emoji}</h3>`;

      // Live
      const speed = Math.round(today.traffic_volume / 10); // optional
      liveContainer.innerHTML += `<h3>${loc}: ${today.congestion} ${emoji} (${speed} km/h)</h3>`;
    }

    liveContainer.innerHTML += `<p>Last Updated: ${new Date().toLocaleTimeString()}</p>`;

  } catch (err) {
    console.error("Compare/Live fetch failed:", err);
  }

  // Refresh every 1 minute
  setTimeout(fetchCompareAndLive, 60000, allLocations);
}
