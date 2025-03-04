document.addEventListener('DOMContentLoaded', function() {
  // DOM Elements
  const manualRoute = document.getElementById('manualRoute');
  const manualSegment = document.getElementById('manualSegment');
  const loadRouteBtn = document.getElementById('loadRouteBtn');
  const routeSelect = document.getElementById('routeSelect');
  const segmentSelect = document.getElementById('segmentSelect');
  const loadSelectedRouteBtn = document.getElementById('loadSelectedRouteBtn');
  const searchQuery = document.getElementById('searchQuery');
  const searchResults = document.getElementById('searchResults');
  const includeCanData = document.getElementById('includeCanData');
  const autoUpdateChart = document.getElementById('autoUpdateChart');
  const signalList = document.getElementById('signalList');
  const chartTitle = document.getElementById('chartTitle');
  const loadingOverlay = document.getElementById('loadingOverlay');
  const noDataMessage = document.getElementById('noDataMessage');
  const resetZoomBtn = document.getElementById('resetZoomBtn');
  const exportDataBtn = document.getElementById('exportDataBtn');
  const plotChart = document.getElementById('plotChart');

  // Global variables
  let chart = null;
  let selectedSignals = new Set();
  let currentRoute = '';
  let currentSegment = '';
  let logData = null;
  let eventSource = null;
  let colorMap = {};
  let updateInterval = null;

  // Color palette for signals
  const colors = [
    '#4285F4', '#EA4335', '#FBBC05', '#34A853', // Google colors
    '#8BC34A', '#FFC107', '#03A9F4', '#E91E63', // Material colors
    '#9C27B0', '#673AB7', '#3F51B5', '#2196F3',
    '#009688', '#CDDC39', '#FF9800', '#795548',
    '#607D8B', '#D32F2F', '#7CB342', '#FFB300',
  ];

  // =========================================================
  // Helper Functions
  // =========================================================

  // Function to generate a consistent color for a signal
  function getColorForSignal(signalName) {
    if (!colorMap[signalName]) {
      const index = Object.keys(colorMap).length % colors.length;
      colorMap[signalName] = colors[index];
    }
    return colorMap[signalName];
  }

  // Function to format timestamps (convert nanoseconds to milliseconds)
  function formatTimestamp(timestamp) {
    return timestamp / 1000000; // Convert to milliseconds
  }

  // Function to show loading state
  function showLoading(show) {
    loadingOverlay.hidden = !show;
    if (show) {
      noDataMessage.style.display = 'none';
    }
  }

  // Function to save route to recent routes
  function saveRecentRoute(route) {
    fetch('/save_recent_route', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ route: route })
    });
  }

  // Function to load segments for a route
  function loadSegments(route) {
    segmentSelect.disabled = true;
    segmentSelect.innerHTML = '<option value="">Loading segments...</option>';

    console.log(`Loading segments for route: ${route}`);

    fetch(`/segments?route=${encodeURIComponent(route)}`)
      .then(response => {
        console.log('Segments response status:', response.status);
        return response.json();
      })
      .then(data => {
        console.log('Segments response:', data);

        segmentSelect.innerHTML = '<option value="">Select segment</option>';

        if (data.segments && data.segments.length > 0) {
          data.segments.forEach((segment, index) => {
            const option = document.createElement('option');
            option.value = segment; // Use the actual segment number
            option.textContent = `Segment ${segment}`;
            segmentSelect.appendChild(option);
          });
          segmentSelect.disabled = false;
          loadSelectedRouteBtn.disabled = false;
        } else {
          // If we have a message, show it
          const message = data.message || 'No segments found';
          segmentSelect.innerHTML = `<option value="">${message}</option>`;

          // Log debug info
          if (data.debug_info) {
            console.log('Debug info:', data.debug_info);
          }

          // Log route info for debugging
          if (data.route_dir) {
            console.log(`Route directory: ${data.route_dir}`);
          }

          // Allow direct loading even if no segments found
          loadSelectedRouteBtn.disabled = false;

          // If this is just a "no segments found" message but the route exists,
          // we can still try to load segment 0 as a fallback
          if (message.includes('No segments found') || message.includes('No matching route found')) {
            console.log('Adding default segment 0 as fallback');
            const option = document.createElement('option');
            option.value = 0;
            option.textContent = 'Segment 0 (default)';
            segmentSelect.appendChild(option);
            segmentSelect.disabled = false;
          }
        }
      })
      .catch(error => {
        console.error('Error loading segments:', error);
        segmentSelect.innerHTML = '<option value="">Error loading segments</option>';
        // Still allow loading in case of error
        loadSelectedRouteBtn.disabled = false;
      });
  }

  // Function to search routes
  function searchRoutes(query) {
    if (!query.trim()) {
      searchResults.innerHTML = '<div class="uk-alert uk-alert-primary">Enter a search term above</div>';
      return;
    }

    searchResults.innerHTML = '<div class="uk-text-center"><div uk-spinner></div><p>Searching...</p></div>';

    fetch(`/search_routes?query=${encodeURIComponent(query)}`)
      .then(response => response.json())
      .then(data => {
        if (data.routes && data.routes.length > 0) {
          const resultsList = document.createElement('ul');
          resultsList.className = 'uk-list uk-list-divider';

          data.routes.forEach(route => {
            const li = document.createElement('li');
            const link = document.createElement('a');
            link.href = '#';
            link.textContent = route;
            link.dataset.route = route;
            link.className = 'search-route';
            link.addEventListener('click', function(e) {
              e.preventDefault();
              manualRoute.value = route;
              document.querySelector('.uk-tab li:first-child a').click();
            });

            li.appendChild(link);
            resultsList.appendChild(li);
          });

          searchResults.innerHTML = '';
          searchResults.appendChild(resultsList);
        } else {
          searchResults.innerHTML = '<div class="uk-alert uk-alert-warning">No routes found</div>';
        }
      })
      .catch(error => {
        console.error('Error searching routes:', error);
        searchResults.innerHTML = '<div class="uk-alert uk-alert-danger">Error searching routes</div>';
      });
  }

  // Function to populate signal list from data
  function populateSignalList(data) {
    signalList.innerHTML = '';
    const signalTree = document.createElement('ul');
    signalTree.className = 'uk-list uk-list-divider';

    // Sort message types alphabetically
    const messageTypes = Object.keys(data).sort();

    messageTypes.forEach(msgType => {
      const li = document.createElement('li');

      // Create message type header with toggle
      const header = document.createElement('div');
      header.className = 'uk-flex uk-flex-middle uk-margin-small-bottom';

      const toggle = document.createElement('span');
      toggle.setAttribute('uk-icon', 'icon: triangle-right');
      toggle.className = 'uk-margin-small-right message-toggle';
      toggle.style.cursor = 'pointer';

      const msgName = document.createElement('span');
      msgName.textContent = msgType;
      msgName.className = 'uk-text-bold';

      header.appendChild(toggle);
      header.appendChild(msgName);
      li.appendChild(header);

      // Create collapsible content for fields
      const fieldsContainer = document.createElement('div');
      fieldsContainer.className = 'fields-container uk-margin-left';
      fieldsContainer.style.display = 'none';

      const fieldsList = document.createElement('ul');
      fieldsList.className = 'uk-list uk-list-small';

      // Get fields from the data
      const fields = Object.keys(data[msgType].values).sort();

      fields.forEach(field => {
        const fieldLi = document.createElement('li');

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.className = 'uk-checkbox signal-checkbox';
        checkbox.dataset.msgType = msgType;
        checkbox.dataset.field = field;
        checkbox.id = `${msgType}-${field}`;

        const label = document.createElement('label');
        label.htmlFor = `${msgType}-${field}`;
        label.textContent = ` ${field}`;
        label.className = 'uk-margin-small-left';

        // Add event listener to checkbox
        checkbox.addEventListener('change', function() {
          const signalId = `${msgType}.${field}`;
          if (this.checked) {
            selectedSignals.add(signalId);
          } else {
            selectedSignals.delete(signalId);
          }
          updateChart();
        });

        fieldLi.appendChild(checkbox);
        fieldLi.appendChild(label);
        fieldsList.appendChild(fieldLi);
      });

      fieldsContainer.appendChild(fieldsList);
      li.appendChild(fieldsContainer);

      // Add event listener to toggle
      toggle.addEventListener('click', function() {
        const isExpanded = this.getAttribute('uk-icon') === 'icon: triangle-down';
        this.setAttribute('uk-icon', isExpanded ? 'icon: triangle-right' : 'icon: triangle-down');
        fieldsContainer.style.display = isExpanded ? 'none' : 'block';
      });

      signalTree.appendChild(li);
    });

    signalList.appendChild(signalTree);
  }

  // Function to load route data
  function loadRouteData(route, segment = null, includeCanData = false) {
    if (!route) return;

    currentRoute = route;
    currentSegment = segment;

    console.log(`Loading route data: ${route}, segment: ${segment}, includeCanData: ${includeCanData}`);

    // Show loading indicator
    showLoading(true);

    // Update chart title
    chartTitle.textContent = `Loading ${route}${segment !== null ? ' - Segment ' + segment : ''}`;

    // Reset current selection
    selectedSignals.clear();

    // Build URL
    let url = `/web_plotjuggler_data?route=${encodeURIComponent(route)}`;
    if (segment !== null && segment !== '' && segment !== undefined) {
      url += `&segment=${segment}`;
    }
    if (includeCanData) {
      url += '&can=true';
    }

    console.log('Fetching data from:', url);

    // Fetch data
    fetch(url)
      .then(response => {
        console.log('Data response status:', response.status);
        if (!response.ok) {
          throw new Error(`Network response was not ok: ${response.status} ${response.statusText}`);
        }
        return response.json();
      })
      .then(data => {
        console.log('Data response received:', Object.keys(data));

        if (data.success) {
          logData = data.data;

          // Check if we actually got meaningful data
          if (Object.keys(logData).length === 0) {
            throw new Error('No data found in the response');
          }

          // Save to recent routes
          saveRecentRoute(route);

          // Update UI
          chartTitle.textContent = `${route}${segment !== null ? ' - Segment ' + segment : ''}`;
          noDataMessage.style.display = 'none';
          resetZoomBtn.disabled = false;
          exportDataBtn.disabled = false;

          // Populate signal list
          populateSignalList(logData);

          // Create an empty chart initially
          createChart();

          // Set up auto-update if needed
          setupAutoUpdate();
        } else {
          // Check if we have an error message
          const errorMsg = data.error || 'Failed to load data';
          console.error('Error from server:', errorMsg);

          // Check if there's additional debug info
          if (data.debug_info) {
            console.log('Debug info:', data.debug_info);
          }

          throw new Error(errorMsg);
        }
      })
      .catch(error => {
        console.error('Error loading data:', error);
        chartTitle.textContent = 'Error: ' + error.message;
        noDataMessage.style.display = 'block';
        noDataMessage.innerHTML = `
          <span uk-icon="icon: warning; ratio: 3"></span>
          <p class="uk-margin-small-top">Failed to load data: ${error.message}</p>
          <p class="uk-text-small">Check browser console for more details.</p>
        `;
      })
      .finally(() => {
        showLoading(false);
      });
  }

  // Function to create the chart
  function createChart() {
    // Destroy existing chart if it exists
    if (chart) {
      chart.destroy();
    }

    // Create new chart
    chart = new Chart(plotChart, {
      type: 'line',
      data: {
        datasets: []
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: false,
        interaction: {
          mode: 'nearest',
          axis: 'x',
          intersect: false
        },
        scales: {
          x: {
            type: 'time',
            time: {
              unit: 'millisecond',
              displayFormats: {
                millisecond: 'mm:ss.SSS'
              }
            },
            title: {
              display: true,
              text: 'Time'
            }
          },
          y: {
            title: {
              display: true,
              text: 'Value'
            }
          }
        },
        plugins: {
          zoom: {
            pan: {
              enabled: true,
              mode: 'xy'
            },
            zoom: {
              wheel: {
                enabled: true,
              },
              pinch: {
                enabled: true
              },
              mode: 'xy',
            }
          },
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 12,
              usePointStyle: true
            }
          },
          tooltip: {
            callbacks: {
              title: function(tooltipItems) {
                return moment(tooltipItems[0].parsed.x).format('mm:ss.SSS');
              }
            }
          }
        }
      }
    });
  }

  // Function to update chart with selected signals
  function updateChart() {
    if (!chart || !logData || selectedSignals.size === 0) return;

    // Clear existing datasets
    chart.data.datasets = [];

    // Add selected signals to chart
    selectedSignals.forEach(signalId => {
      const [msgType, field] = signalId.split('.');
      if (logData[msgType] && logData[msgType].values[field]) {
        const timestamps = logData[msgType].timestamps.map(formatTimestamp);
        const values = logData[msgType].values[field];

        // Create dataset
        chart.data.datasets.push({
          label: `${msgType}.${field}`,
          data: timestamps.map((t, i) => ({ x: t, y: values[i] })),
          borderColor: getColorForSignal(signalId),
          backgroundColor: getColorForSignal(signalId) + '20', // Add transparency
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.1
        });
      }
    });

    // Update chart
    chart.update();
  }

  // Function to setup auto-update
  function setupAutoUpdate() {
    // Clear existing interval
    if (updateInterval) {
      clearInterval(updateInterval);
      updateInterval = null;
    }

    // Clear existing event source
    if (eventSource) {
      eventSource.close();
      eventSource = null;
    }

    // If auto-update is enabled, setup SSE
    if (autoUpdateChart.checked) {
      // Create event source
      const url = `/web_plotjuggler_stream?route=${encodeURIComponent(currentRoute)}`;
      eventSource = new EventSource(url);

      // Handle connection open
      eventSource.addEventListener('open', function(e) {
        console.log('SSE connection established');
      });

      // Handle data events
      eventSource.addEventListener('data', function(e) {
        const newData = JSON.parse(e.data);
        console.log('Received new data:', newData);

        // In a real implementation, you would:
        // 1. Update logData with new values
        // 2. Update the chart with the new data points
        // 3. Remove old data points if needed
      });

      // Handle errors
      eventSource.addEventListener('error', function(e) {
        console.error('SSE error:', e);
        eventSource.close();
      });
    }
  }

  // Function to reset zoom
  function resetZoom() {
    if (chart) {
      chart.resetZoom();
    }
  }

  // Function to export data
  function exportData() {
    if (!logData) return;

    // Create a filtered version of the data with only selected signals
    const exportData = {};
    selectedSignals.forEach(signalId => {
      const [msgType, field] = signalId.split('.');
      if (logData[msgType] && logData[msgType].values[field]) {
        if (!exportData[msgType]) {
          exportData[msgType] = {
            timestamps: logData[msgType].timestamps,
            values: {}
          };
        }
        exportData[msgType].values[field] = logData[msgType].values[field];
      }
    });

    // Create JSON string
    const jsonString = JSON.stringify(exportData, null, 2);

    // Create download link
    const blob = new Blob([jsonString], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${currentRoute}${currentSegment ? '_segment_' + currentSegment : ''}_data.json`;
    document.body.appendChild(a);
    a.click();

    // Cleanup
    setTimeout(() => {
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    }, 100);
  }

  // =========================================================
  // Event Listeners
  // =========================================================

  // Manual route load button
  loadRouteBtn.addEventListener('click', function() {
    const route = manualRoute.value.trim();
    const segment = manualSegment.value.trim();
    console.log(`Load button clicked for route: ${route}, segment: ${segment}`);
    loadRouteData(route, segment, includeCanData.checked);
  });

  // Route select dropdown
  routeSelect.addEventListener('change', function() {
    const route = this.value;
    console.log(`Route selected: ${route}`);
    if (route) {
      loadSegments(route);
    } else {
      segmentSelect.disabled = true;
      loadSelectedRouteBtn.disabled = true;
    }
  });

  // Load selected route button
  loadSelectedRouteBtn.addEventListener('click', function() {
    const route = routeSelect.value;
    const segment = segmentSelect.value;
    console.log(`Load selected route button clicked for route: ${route}, segment: ${segment}`);
    if (route) {
      loadRouteData(route, segment, includeCanData.checked);
    }
  });

  // Search input
  searchQuery.addEventListener('keyup', function(e) {
    if (e.key === 'Enter') {
      searchRoutes(this.value);
    }
  });

  // Recent routes
  document.addEventListener('click', function(e) {
    if (e.target.classList.contains('recent-route')) {
      e.preventDefault();
      const route = e.target.dataset.route;
      manualRoute.value = route;
      document.querySelector('.uk-tab li:first-child a').click();
    }
  });

  // Include CAN data checkbox
  includeCanData.addEventListener('change', function() {
    if (currentRoute) {
      loadRouteData(currentRoute, currentSegment, this.checked);
    }
  });

  // Auto-update checkbox
  autoUpdateChart.addEventListener('change', function() {
    setupAutoUpdate();
  });

  // Reset zoom button
  resetZoomBtn.addEventListener('click', resetZoom);

  // Export data button
  exportDataBtn.addEventListener('click', exportData);

  // =========================================================
  // Initialization
  // =========================================================

  // Log initial state for debugging
  console.log('Web PlotJuggler initialized');
  console.log('Available routes:', available_routes ? available_routes.length : 'none');

  // Initialize the chart with empty data
  createChart();

  // If route is specified in URL, load it automatically
  const urlParams = new URLSearchParams(window.location.search);
  const routeParam = urlParams.get('route');
  const segmentParam = urlParams.get('segment');

  console.log(`URL params - route: ${routeParam}, segment: ${segmentParam}`);

  if (routeParam) {
    console.log(`Auto-loading route from URL: ${routeParam}`);
    manualRoute.value = routeParam;
    if (segmentParam) {
      manualSegment.value = segmentParam;
    }
    // Delay the auto-load to ensure DOM is fully initialized
    setTimeout(() => {
      loadRouteBtn.click();
    }, 500);
  }
});