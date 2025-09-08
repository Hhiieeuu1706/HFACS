document.addEventListener('DOMContentLoaded', function () {

    const socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);

    // --- DOM Elements ---
    const loadingOverlay = document.getElementById('loading-overlay');
    const audioStatusIcon = document.getElementById('audio-status-icon');
    const flightStatusIndicator = document.getElementById('flight-status-indicator');
    const phaseEl = document.getElementById('phase');
    const altitudeEl = document.getElementById('altitude');
    const airspeedEl = document.getElementById('airspeed');
    const gForceEl = document.getElementById('g-force');
    const progressBar = document.getElementById('progress-bar');
    const occMessagesEl = document.getElementById('occ-messages');
    const efbMessagesEl = document.getElementById('efb-messages');
    const anomalyLogCard = document.getElementById('anomaly-log-card');
    const anomalyLogList = document.getElementById('anomaly-log-list');
    const drilldownModal = new bootstrap.Modal(document.getElementById('drilldownModal'));
    const drilldownChartImg = document.getElementById('drilldown-chart-img');
    const drilldownModalLabel = document.getElementById('drilldownModalLabel');
    const currentGForceEl = document.getElementById('current-g-force');
    const maxGForceEl = document.getElementById('max-g-force');
    const minGForceEl = document.getElementById('min-g-force');
    const procedureGuidanceCard = document.getElementById('procedure-guidance-card');
    const procedureGuidanceList = document.getElementById('procedure-guidance-list');
    const runSimulationBtn = document.getElementById('run-simulation-btn');

    

    // --- State Management ---
    let lastOccMessage = '';
    let lastEfbMessage = '';
    let maxGForce = -Infinity;
    let minGForce = Infinity;
    let chartAnnotations = {}; // To store annotations for Chart.js

    // --- Audio Context for Beep Sound ---
    let audioCtx;
    function initAudio() {
        if (!audioCtx) {
            try {
                audioCtx = new (window.AudioContext || window.webkitAudioContext)();
                audioStatusIcon.classList.replace('fa-volume-mute', 'fa-volume-up');
                audioStatusIcon.style.color = 'var(--accent-green)';
                audioStatusIcon.title = 'Audio Enabled';
            } catch (e) {
                audioStatusIcon.title = 'Audio Not Supported';
                audioStatusIcon.style.color = 'var(--accent-red)';
            }
        }
        document.removeEventListener('click', initAudio);
    }
    document.addEventListener('click', initAudio);

    function playBeep() {
        if (!audioCtx) return;
        if (audioCtx.state === 'suspended') audioCtx.resume();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();
        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);
        oscillator.type = 'sine';
        oscillator.frequency.setValueAtTime(880, audioCtx.currentTime);
        gainNode.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.0001, audioCtx.currentTime + 0.15);
        oscillator.start(audioCtx.currentTime);
        oscillator.stop(audioCtx.currentTime + 0.15);
    }

    // --- Chart.js Config ---
    Chart.defaults.color = '#adb5bd';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.1)';
    const ctx = document.getElementById('telemetryChart').getContext('2d');
    const telemetryChart = new Chart(ctx, {
        type: 'line',
        data: { labels: [], datasets: [
            { label: 'Altitude (ft)', data: [], borderColor: '#3a7bd5', yAxisID: 'y', tension: 0.2, pointRadius: 0, borderWidth: 2 },
            { label: 'Airspeed (kts)', data: [], borderColor: '#28a745', yAxisID: 'y1', tension: 0.2, pointRadius: 0, borderWidth: 2 }
        ]},
        options: {
            responsive: true, maintainAspectRatio: false, animation: false,
            interaction: { mode: 'index', intersect: false },
            scales: {
                x: { type: 'linear', title: { display: true, text: 'Time (s)', color: '#e9ecef' }, min: 0, max: 135 },
                y: { type: 'linear', display: true, position: 'left', title: { display: true, text: 'Altitude', color: '#e9ecef' }, min: 0, grid: { color: 'rgba(255, 255, 255, 0.1)' } },
                y1: { type: 'linear', display: true, position: 'right', title: { display: true, text: 'Airspeed', color: '#e9ecef' }, min: 0, grid: { drawOnChartArea: false } }
            },
            plugins: {
                legend: { position: 'top', labels: { color: '#e9ecef' } },
                tooltip: { enabled: true, backgroundColor: 'rgba(0, 0, 0, 0.8)', titleColor: '#ffffff', bodyColor: '#ffffff' },
                annotation: { annotations: chartAnnotations }
            }
        }
    });

    // --- Socket.IO Handlers ---
    socket.on('connect', () => {
        loadingOverlay.classList.add('hidden'); // Hide loading overlay on connect
        document.body.style.overflow = 'auto'; // Re-enable scrolling
        // Simulation will now be started by button click
    });

    socket.on('simulation_metadata', (data) => {
        // --- FIX: Hide loading overlay when simulation is ready to start streaming ---
        loadingOverlay.classList.add('hidden');
        document.body.style.overflow = 'auto';

        telemetryChart.options.scales.x.max = data.max_timestamp;
        telemetryChart.options.scales.y.max = data.max_altitude;
        telemetryChart.options.scales.y1.max = data.max_airspeed;
        telemetryChart.update();
    });

    socket.on('hfacs_results', (data) => {
        // Display HFACS results on the dashboard if you have a dedicated area
        console.log("HFACS Results:", data);
        // Example: You might want to update a specific div with these results
        // document.getElementById('hfacs-level').textContent = data.hfacs_level;
        // document.getElementById('hfacs-confidence').textContent = data.hfacs_confidence;
        // document.getElementById('hfacs-reasoning').textContent = data.hfacs_reasoning;
    });

    socket.on('update', (data) => {
        if (data.error) { console.error(data.error); return; }

        // 1. Update Header and Metrics
        flightStatusIndicator.className = `status-${data.flight_status.toLowerCase()} me-3`;
        flightStatusIndicator.title = `Flight Status: ${data.flight_status}`;
        phaseEl.textContent = data.phase;
        altitudeEl.textContent = data.altitude;
        airspeedEl.textContent = data.airspeed;
        gForceEl.textContent = data.g_force;
        progressBar.style.width = (data.timestamp / telemetryChart.options.scales.x.max) * 100 + '%';

        // 2. Update G-Force Monitor
        currentGForceEl.textContent = data.g_force;
        if (data.g_force > maxGForce) maxGForce = data.g_force;
        if (data.g_force < minGForce) minGForce = data.g_force;
        maxGForceEl.textContent = maxGForce.toFixed(1);
        minGForceEl.textContent = minGForce.toFixed(1);
        // Change color based on exceedance (using thresholds from backend)
        if (data.g_force > 1.5 || data.g_force < 0.5) { // Hardcoded for now, ideally from backend
            currentGForceEl.classList.add('g-exceeded');
            currentGForceEl.classList.remove('g-normal');
        } else {
            currentGForceEl.classList.add('g-normal');
            currentGForceEl.classList.remove('g-exceeded');
        }

        // 3. Update Message Lists
        updateMessageList(occMessagesEl, data.occ_messages, true);
        updateMessageList(efbMessagesEl, data.efb_messages, false);

        // 4. Handle Anomaly Log, Sound, and Chart Annotation
        if (data.anomaly_details) {
            playBeep();
            const details = data.anomaly_details;
            const li = document.createElement('li');
            li.className = 'list-group-item log-clickable';
            if (details.priority === 'HIGH') {
                li.classList.add('priority-high');
            }
            li.innerHTML = `<strong>${details.friendly_name}</strong> at ${details.timestamp}s<br><small class="text-muted">Click to see analysis chart</small>`;
            li.dataset.chartUrl = details.chart_url;
            li.dataset.anomalyName = details.friendly_name;
            anomalyLogList.appendChild(li);
            anomalyLogCard.style.display = 'block';

            // Add annotation to chart
            const annotationId = `anomaly-${details.timestamp}`;
            chartAnnotations[annotationId] = {
                type: 'line',
                mode: 'vertical',
                scaleID: 'x',
                value: details.timestamp,
                borderColor: 'var(--accent-red)',
                borderWidth: 2,
                label: {
                    content: details.friendly_name,
                    enabled: true,
                    position: 'top',
                    backgroundColor: 'rgba(220, 53, 69, 0.8)',
                    color: 'white',
                    font: { size: 10, weight: 'bold' },
                    yAdjust: -10
                }
            };
            telemetryChart.update();
        }

        // 5. Handle Procedural Guidance
        if (data.procedures && data.procedures.length > 0) {
            procedureGuidanceList.innerHTML = '';
            data.procedures.forEach(step => {
                const li = document.createElement('li');
                li.className = 'list-group-item';
                li.textContent = step;
                procedureGuidanceList.appendChild(li);
            });
            procedureGuidanceCard.style.display = 'block';
        } else {
            procedureGuidanceCard.style.display = 'none';
        }

        // 6. Update Chart
        telemetryChart.data.labels.push(data.timestamp);
        telemetryChart.data.datasets[0].data.push(data.altitude);
        telemetryChart.data.datasets[1].data.push(data.airspeed);
        telemetryChart.update();
    });

    // --- Event Listeners ---
    runSimulationBtn.addEventListener('click', function() {
        resetDashboard();
        socket.emit('start_simulation');
    });

    anomalyLogList.addEventListener('click', function(e) {
        const targetLi = e.target.closest('.log-clickable');
        if (targetLi && targetLi.dataset.chartUrl) {
            drilldownModalLabel.textContent = `Analysis for: ${targetLi.dataset.anomalyName}`;
            drilldownChartImg.src = targetLi.dataset.chartUrl;
            drilldownModal.show();
        }
    });

    // --- Helper Functions ---
    function updateMessageList(element, messages, isOcc) {
        const newMessagesContent = messages.join('\n');
        let lastMessagesContent = isOcc ? lastOccMessage : lastEfbMessage;

        if (newMessagesContent === lastMessagesContent) {
            return; // Do nothing if content hasn't changed
        }

        const messageItems = messages.map(msg => {
            let itemClass = 'list-group-item';
            if (msg.includes('ALERT') || msg.includes('ECAM')) {
                itemClass += ' list-group-item-danger';
            }
            if (isOcc && msg.includes('nominal')) {
                itemClass += ' list-group-item-success';
            }
            if (isOcc && msg.includes('CRITICAL')) {
                itemClass += ' priority-high';
            }
            return `<li class="${itemClass}">${msg}</li>`;
        });
        element.innerHTML = messageItems.join(''); // Set innerHTML once
        
        if (isOcc) {
            lastOccMessage = newMessagesContent;
        } else {
            lastEfbMessage = newMessagesContent;
        }
    }

    function resetDashboard() {
        // Reset metrics
        altitudeEl.textContent = '0';
        airspeedEl.textContent = '0';
        gForceEl.textContent = '0';
        phaseEl.textContent = '-';
        progressBar.style.width = '0%';
        flightStatusIndicator.className = 'status-green me-3';
        flightStatusIndicator.title = 'Flight Status';

        // Reset G-Force monitor
        currentGForceEl.textContent = '1.0';
        maxGForceEl.textContent = '1.0';
        minGForceEl.textContent = '1.0';
        currentGForceEl.classList.remove('g-exceeded');
        currentGForceEl.classList.add('g-normal');
        maxGForce = -Infinity;
        minGForce = Infinity;

        // Clear messages
        occMessagesEl.innerHTML = '';
        efbMessagesEl.innerHTML = '';
        anomalyLogList.innerHTML = '';
        anomalyLogCard.style.display = 'none';
        procedureGuidanceList.innerHTML = '';
        procedureGuidanceCard.style.display = 'none';
        lastOccMessage = '';
        lastEfbMessage = '';

        // Clear chart data and annotations
        telemetryChart.data.labels = [];
        telemetryChart.data.datasets[0].data = [];
        telemetryChart.data.datasets[1].data = [];
        chartAnnotations = {};
        telemetryChart.options.plugins.annotation.annotations = chartAnnotations;
        telemetryChart.update();

        // Show loading overlay again
        loadingOverlay.classList.remove('hidden');
        document.body.style.overflow = 'hidden';
        document.getElementById('loading-message').textContent = 'Starting new simulation...';
    }
});