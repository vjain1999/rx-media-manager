// Restaurant Video Analyzer - Frontend JavaScript
class RestaurantAnalyzer {
    constructor() {
        this.socket = io();
        this.currentResults = null;
        this.initTabs();
        this.initEventListeners();
        this.initSocketListeners();
    }

    initEventListeners() {
        // Form submission
        document.getElementById('restaurantForm').addEventListener('submit', (e) => {
            e.preventDefault();
            this.startAnalysis();
        });

        // Send SMS button
        document.getElementById('sendSmsBtn').addEventListener('click', () => {
            this.sendSMS();
        });

        // Close modal
        document.getElementById('closeModal').addEventListener('click', () => {
            this.hideModal();
        });

        // IG handle form
        const igForm = document.getElementById('igForm');
        if (igForm) {
            igForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.findIGHandle();
            });
        }

        // Frames form
        const framesForm = document.getElementById('framesForm');
        if (framesForm) {
            framesForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.analyzeFrames();
            });
        }

        // Bulk IG upload
        const bulkBtn = document.getElementById('igBulkUploadBtn');
        if (bulkBtn) {
            bulkBtn.addEventListener('click', () => this.processBulkIG());
        }
        const downloadBtn = document.getElementById('igBulkDownloadBtn');
        if (downloadBtn) {
            downloadBtn.addEventListener('click', () => this.downloadBulkCSV());
        }
    }

    initSocketListeners() {
        this.socket.on('connect', () => {
            console.log('Connected to server');
        });

        this.socket.on('progress_update', (data) => {
            this.updateProgress(data);
        });

        this.socket.on('processing_complete', (results) => {
            this.showResults(results);
        });
    }

    initTabs() {
        const tabs = {
            tabBtnFull: 'tab-full',
            tabBtnIG: 'tab-ig',
            tabBtnFrames: 'tab-frames'
        };
        const setActive = (btnId) => {
            Object.entries(tabs).forEach(([buttonId, tabId]) => {
                const btn = document.getElementById(buttonId);
                const tab = document.getElementById(tabId);
                if (!btn || !tab) return;
                const active = buttonId === btnId;
                tab.style.display = active ? 'grid' : 'none';
                btn.classList.toggle('bg-blue-600', active);
                btn.classList.toggle('text-white', active);
                btn.classList.toggle('text-gray-700', !active);
            });
        };
        ['tabBtnFull','tabBtnIG','tabBtnFrames'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('click', () => setActive(id));
        });
        // Default
        setActive('tabBtnFull');
    }

    startAnalysis() {
        const formData = {
            restaurant_name: document.getElementById('restaurantName').value.trim(),
            address: document.getElementById('address').value.trim(),
            phone: document.getElementById('phone').value.trim(),
            min_score: parseFloat(document.getElementById('minScore').value)
        };

        // Validate form
        if (!formData.restaurant_name || !formData.address || !formData.phone) {
            this.showModal('error', 'Error', 'Please fill in all required fields.');
            return;
        }

        // Show progress container
        document.getElementById('progressContainer').style.display = 'block';
        document.getElementById('resultsContainer').style.display = 'none';
        
        // Disable form
        this.toggleForm(false);
        
        // Clear previous progress
        this.clearProgress();

        // Start processing via WebSocket
        this.socket.emit("start_processing", formData);    }

    findIGHandle() {
        const name = document.getElementById('igRestaurantName').value.trim();
        const address = document.getElementById('igAddress').value.trim();
        const phone = (document.getElementById('igPhone').value || '').trim();
        if (!name || !address) {
            this.showModal('error', 'Missing info', 'Please enter restaurant name and address.');
            return;
        }
        const btn = document.getElementById('igFindBtn');
        const original = btn.innerHTML;
        btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Searching...';
        fetch('/api/find_instagram', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ restaurant_name: name, address, phone })
        })
        .then(r => r.json())
        .then(data => {
            const el = document.getElementById('igResult');
            if (data.error) {
                el.innerHTML = `<div class="text-red-600">${data.error}</div>`;
            } else {
                const handle = data.instagram_handle;
                const url = handle ? `https://www.instagram.com/${handle}/` : '';
                el.innerHTML = handle ? `Found: <a href="${url}" target="_blank" class="text-blue-600 hover:underline">@${handle}</a>` : 'No handle found';
            }
        })
        .catch(err => {
            console.error(err);
            this.showModal('error', 'Error', 'Failed to search.');
        })
        .finally(() => { btn.disabled = false; btn.innerHTML = original; });
    }

    analyzeFrames() {
        const fileInput = document.getElementById('videoFile');
        const caption = (document.getElementById('videoCaption').value || '').trim();
        if (!fileInput.files || fileInput.files.length === 0) {
            this.showModal('error', 'Missing file', 'Please choose a video file.');
            return;
        }
        const btn = document.getElementById('framesAnalyzeBtn');
        const original = btn.innerHTML;
        btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Analyzing...';
        const form = new FormData();
        form.append('video', fileInput.files[0]);
        form.append('caption', caption);
        fetch('/api/analyze_frames', { method: 'POST', body: form })
            .then(r => r.json())
            .then(data => {
                const el = document.getElementById('framesResult');
                if (data.error) {
                    el.innerHTML = `<div class="text-red-600">${data.error}</div>`;
                } else {
                    el.innerHTML = `<pre class="text-sm bg-gray-50 p-3 rounded-lg overflow-x-auto">${JSON.stringify(data, null, 2)}</pre>`;
                }
            })
            .catch(err => {
                console.error(err);
                this.showModal('error', 'Error', 'Frame analysis failed.');
            })
            .finally(() => { btn.disabled = false; btn.innerHTML = original; });
    }

    processBulkIG() {
        const fileInput = document.getElementById('igBulkFile');
        const file = fileInput && fileInput.files && fileInput.files[0];
        if (!file) {
            this.showModal('error', 'Missing file', 'Please choose a CSV file.');
            return;
        }
        const btn = document.getElementById('igBulkUploadBtn');
        const original = btn.innerHTML;
        btn.disabled = true; btn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processing...';
        const form = new FormData();
        form.append('file', file);
        fetch('/api/bulk_find_instagram', { method: 'POST', body: form })
            .then(r => r.json())
            .then(data => {
                if (data.error) {
                    this.showModal('error', 'Bulk Error', data.error);
                    return;
                }
                this._bulkJobId = data.job_id;
                this._bulkResults = [];
                this._startBulkPolling();
            })
            .catch(err => {
                console.error(err);
                this.showModal('error', 'Error', 'Bulk processing failed.');
            })
            .finally(() => { btn.disabled = false; btn.innerHTML = original; });
    }

    _startBulkPolling() {
        const el = document.getElementById('igBulkResult');
        const dlBtn = document.getElementById('igBulkDownloadBtn');
        const progressLabel = document.createElement('div');
        progressLabel.id = 'bulkProgressLabel';
        progressLabel.className = 'text-sm text-gray-600 mb-2';
        progressLabel.textContent = 'Processing restaurants...';
        
        const progress = document.createElement('div');
        progress.id = 'bulkProgressBar';
        progress.className = 'w-full bg-gray-200 rounded-full h-6 mb-3';
        progress.innerHTML = '<div id="bulkProgressInner" class="bg-blue-600 h-6 rounded-full flex items-center justify-center" style="width:0%"></div>';
        
        el.innerHTML = '';
        el.appendChild(progressLabel);
        el.appendChild(progress);
        this._bulkSeen = 0; // cursor of rows consumed
        const update = () => {
            if (!this._bulkJobId) return;
            const fromParam = (typeof this._bulkSeen === 'number') ? `&from=${this._bulkSeen}` : '';
            fetch(`/api/bulk_status?job_id=${encodeURIComponent(this._bulkJobId)}${fromParam}`)
                .then(r => r.json())
                .then(data => {
                    if (data.error) return;
                    
                    // Update progress bar
                    const inner = document.getElementById('bulkProgressInner');
                    if (inner) {
                        inner.style.width = `${data.percent}%`;
                        // Add text showing progress
                        inner.textContent = `${data.completed || 0}/${data.total || 0} (${data.percent}%)`;
                        inner.style.fontSize = '12px';
                        inner.style.color = 'white';
                        inner.style.fontWeight = 'bold';
                        inner.style.minWidth = '60px'; // Ensure text is visible even at low percentages
                    }
                    
                    // Update progress label
                    const label = document.getElementById('bulkProgressLabel');
                    if (label) {
                        if (data.status === 'done') {
                            label.textContent = 'Processing completed!';
                            label.className = 'text-sm text-green-600 mb-2 font-semibold';
                        } else {
                            const eta = (typeof data.eta_sec === 'number') ? ` • ETA: ${Math.max(0, data.eta_sec)}s` : '';
                            const avg = (typeof data.avg_processing_sec === 'number') ? ` • ~${data.avg_processing_sec.toFixed(1)}s/row` : '';
                            label.textContent = `Processing restaurants... ${data.completed || 0}/${data.total || 0}${avg}${eta}`;
                        }
                    }
                    const latest = data.latest || [];
                    if (Array.isArray(latest) && latest.length) {
                        // append only new rows from server since 'from' cursor
                        this._bulkResults = (this._bulkResults || []).concat(latest);
                        // advance cursor by server-provided next_index (monotonic), fallback to length
                        if (typeof data.next_index === 'number' && data.next_index >= (this._bulkSeen || 0)) {
                            this._bulkSeen = data.next_index;
                        } else {
                            this._bulkSeen = (this._bulkSeen || 0) + latest.length;
                        }
                        el.innerHTML = progressLabel.outerHTML + progress.outerHTML + this.renderBulkTable(this._bulkResults);
                    }
                    if (data.status === 'done') {
                        if (dlBtn) dlBtn.classList.remove('hidden');
                        // Render summary counts
                        try {
                            const allRows = this._bulkResults || [];
                            const totals = {
                                total: allRows.length,
                                ok: allRows.filter(r => r.status === 'ok').length,
                                probable: allRows.filter(r => r.status === 'probable').length,
                                not_found: allRows.filter(r => r.status === 'not_found').length,
                                error: allRows.filter(r => r.status === 'error').length,
                            };
                            const summaryEl = document.getElementById('igBulkSummary');
                            if (summaryEl) {
                                summaryEl.innerHTML = `
                                    <div class="grid grid-cols-2 md:grid-cols-5 gap-3">
                                      <div class="bg-green-50 border border-green-200 rounded-lg p-3 text-center">
                                        <div class="text-xs text-green-800">Success</div>
                                        <div class="text-lg font-semibold text-green-700">${totals.ok}</div>
                                      </div>
                                      <div class="bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-center">
                                        <div class="text-xs text-yellow-800">Probable</div>
                                        <div class="text-lg font-semibold text-yellow-700">${totals.probable}</div>
                                      </div>
                                      <div class="bg-gray-50 border border-gray-200 rounded-lg p-3 text-center">
                                        <div class="text-xs text-gray-700">Not found</div>
                                        <div class="text-lg font-semibold text-gray-800">${totals.not_found}</div>
                                      </div>
                                      <div class="bg-red-50 border border-red-200 rounded-lg p-3 text-center">
                                        <div class="text-xs text-red-800">Errors</div>
                                        <div class="text-lg font-semibold text-red-700">${totals.error}</div>
                                      </div>
                                      <div class="bg-blue-50 border border-blue-200 rounded-lg p-3 text-center col-span-2 md:col-span-1">
                                        <div class="text-xs text-blue-800">Total</div>
                                        <div class="text-lg font-semibold text-blue-700">${totals.total}</div>
                                      </div>
                                    </div>`;
                            }
                        } catch (_) {}
                        this._bulkPoller && clearInterval(this._bulkPoller);
                        // Force final percent to 100% on completion
                        const inner = document.getElementById('bulkProgressInner');
                        if (inner) {
                            inner.style.width = '100%';
                            inner.textContent = `${data.total || allRows.length}/${data.total || allRows.length} (100%)`;
                        }
                    }
                })
                .catch(() => {});
        };
        update();
        this._bulkPoller = setInterval(update, 1500);
    }

    renderBulkTable(rows) {
        if (!rows || rows.length === 0) return '<div class="text-gray-500">No results.</div>';
        const headers = ['business_id','store_id','restaurant_name','address','phone','instagram_handle','status','confidence_grade','confidence_score','message'];
        const thead = '<thead><tr>' + headers.map(h => {
            // Format header names for better display
            const displayName = h.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
            return `<th class="px-3 py-2 text-left border-b text-xs font-semibold text-gray-600">${displayName}</th>`;
        }).join('') + '</tr></thead>';
        
        const tbody = '<tbody>' + rows.map(r => '<tr class="hover:bg-gray-50">' + headers.map(h => {
            let cellValue = (r[h] ?? '').toString();
            let cellClass = 'px-3 py-2 border-b text-sm';
            
            // Special formatting for certain columns
            if (h === 'confidence_grade') {
                const grade = cellValue;
                let gradeClass = 'px-2 py-1 rounded text-xs font-semibold ';
                if (grade === 'High') {
                    gradeClass += 'bg-green-100 text-green-800';
                } else if (grade === 'Medium') {
                    gradeClass += 'bg-yellow-100 text-yellow-800';
                } else if (grade === 'Low') {
                    gradeClass += 'bg-red-100 text-red-800';
                } else {
                    gradeClass += 'bg-gray-100 text-gray-800';
                }
                cellValue = `<span class="${gradeClass}">${grade}</span>`;
            } else if (h === 'confidence_score') {
                const score = parseFloat(cellValue);
                if (!isNaN(score)) {
                    cellValue = `${score.toFixed(1)}%`;
                }
            } else if (h === 'status') {
                const status = cellValue;
                let statusClass = 'px-2 py-1 rounded text-xs font-medium ';
                if (status === 'ok') {
                    statusClass += 'bg-green-100 text-green-800';
                } else if (status === 'probable') {
                    statusClass += 'bg-yellow-100 text-yellow-800';
                } else if (status === 'not_found') {
                    statusClass += 'bg-gray-100 text-gray-800';
                } else if (status === 'error') {
                    statusClass += 'bg-red-100 text-red-800';
                }
                cellValue = `<span class="${statusClass}">${status}</span>`;
            } else if (h === 'instagram_handle' && cellValue) {
                // Make Instagram handles clickable
                cellValue = `<a href="https://www.instagram.com/${cellValue.replace('@', '')}/" target="_blank" class="text-blue-600 hover:underline">@${cellValue.replace('@', '')}</a>`;
            }
            
            return `<td class="${cellClass}">${cellValue}</td>`;
        }).join('') + '</tr>').join('') + '</tbody>';
        
        return `<div class="overflow-x-auto"><table class="min-w-full">${thead}${tbody}</table></div>`;
    }

    downloadBulkCSV() {
        if (!this._bulkJobId) {
            this.showModal('error', 'Error', 'No bulk job to download.');
            return;
        }
        
        // Use server endpoint for downloading CSV
        const downloadUrl = `/api/bulk_download?job_id=${encodeURIComponent(this._bulkJobId)}`;
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `ig_handles_${this._bulkJobId}.csv`;
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    }

    updateProgress(data) {
        const { step, status, message, progress_percent, data: stepData } = data;
        
        // Update progress bar
        document.getElementById('progressPercent').textContent = `${progress_percent}%`;
        document.getElementById('progressBar').style.width = `${progress_percent}%`;

        // Get or create step element
        let stepElement = document.getElementById(`step-${step}`);
        if (!stepElement) {
            stepElement = this.createProgressStep(step, message);
            document.getElementById('progressSteps').appendChild(stepElement);
        }

        // Update step status
        this.updateProgressStep(stepElement, status, message, stepData);

        // Scroll to current step
        stepElement.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    createProgressStep(step, message) {
        const stepElement = document.createElement('div');
        stepElement.id = `step-${step}`;
        stepElement.className = 'progress-step flex items-center p-4 bg-gray-50 rounded-lg border-l-4 border-gray-300';
        
        stepElement.innerHTML = `
            <div class="flex-shrink-0 w-8 h-8 rounded-full bg-gray-300 flex items-center justify-center mr-4">
                <span class="step-number text-sm font-semibold text-gray-600">${step}</span>
                <i class="step-icon hidden"></i>
            </div>
            <div class="flex-1">
                <p class="step-message text-gray-700 font-medium">${message}</p>
                <div class="step-details text-sm text-gray-500 mt-1 hidden"></div>
            </div>
            <div class="step-status">
                <i class="fas fa-clock text-gray-400"></i>
            </div>
        `;

        return stepElement;
    }

    updateProgressStep(stepElement, status, message, data) {
        const stepNumber = stepElement.querySelector('.step-number');
        const stepIcon = stepElement.querySelector('.step-icon');
        const stepMessage = stepElement.querySelector('.step-message');
        const stepDetails = stepElement.querySelector('.step-details');
        const stepStatus = stepElement.querySelector('.step-status i');

        // Update message
        stepMessage.textContent = message;

        // Remove existing status classes
        stepElement.classList.remove('step-active', 'step-completed', 'step-error');
        stepElement.classList.remove('border-blue-500', 'border-green-500', 'border-red-500', 'border-gray-300');

        switch (status) {
            case 'in_progress':
                stepElement.classList.add('step-active', 'border-blue-500');
                stepStatus.className = 'fas fa-spinner fa-spin text-blue-500';
                stepElement.style.background = 'linear-gradient(135deg, #dbeafe, #bfdbfe)';
                break;
                
            case 'completed':
                stepElement.classList.add('step-completed', 'border-green-500');
                stepNumber.style.display = 'none';
                stepIcon.style.display = 'block';
                stepIcon.className = 'step-icon fas fa-check text-white';
                stepStatus.className = 'fas fa-check-circle text-green-500';
                stepElement.style.background = 'linear-gradient(135deg, #d1fae5, #a7f3d0)';
                
                // Show additional details
                if (data) {
                    this.showStepDetails(stepDetails, data);
                }
                break;
                
            case 'error':
                stepElement.classList.add('step-error', 'border-red-500');
                stepNumber.style.display = 'none';
                stepIcon.style.display = 'block';
                stepIcon.className = 'step-icon fas fa-times text-white';
                stepStatus.className = 'fas fa-exclamation-circle text-red-500';
                stepElement.style.background = 'linear-gradient(135deg, #fee2e2, #fecaca)';
                break;
        }
    }

    showStepDetails(detailsElement, data) {
        let details = '';
        
        if (data.instagram_handle) {
            details += `Instagram: @${data.instagram_handle} `;
        }
        if (data.videos_count) {
            details += `Found ${data.videos_count} videos `;
        }
        if (data.downloaded_count) {
            details += `Downloaded ${data.downloaded_count} videos `;
        }
        if (data.approved_count !== undefined) {
            details += `${data.approved_count} videos approved `;
        }
        
        if (details) {
            detailsElement.textContent = details;
            detailsElement.classList.remove('hidden');
        }
    }

    showResults(results) {
        this.currentResults = results;
        
        // Show results container
        document.getElementById('resultsContainer').style.display = 'block';
        document.getElementById('resultsContainer').scrollIntoView({ behavior: 'smooth' });
        
        // Update summary stats
        this.updateSummaryStats(results);
        
        // Show approved videos
        this.showApprovedVideos(results.approved_videos || []);
        
        // Show SMS preview
        this.showSMSPreview(results.sms_preview || '');
        
        // Re-enable form
        this.toggleForm(true);
    }

    updateSummaryStats(results) {
        const stats = [
            { label: 'Videos Found', value: results.videos_found || 0, icon: 'fa-video', color: 'blue' },
            { label: 'Downloaded', value: results.videos_downloaded || 0, icon: 'fa-download', color: 'indigo' },
            { label: 'Approved', value: results.videos_approved || 0, icon: 'fa-check-circle', color: 'green' },
            { label: 'Quality Score', value: this.getAverageScore(results.approved_videos), icon: 'fa-star', color: 'yellow' }
        ];

        const statsContainer = document.getElementById('summaryStats');
        statsContainer.innerHTML = stats.map(stat => `
            <div class="bg-${stat.color}-50 p-4 rounded-xl text-center">
                <i class="fas ${stat.icon} text-${stat.color}-500 text-2xl mb-2"></i>
                <div class="text-2xl font-bold text-${stat.color}-700">${stat.value}</div>
                <div class="text-sm text-${stat.color}-600">${stat.label}</div>
            </div>
        `).join('');
    }

    getAverageScore(videos) {
        if (!videos || videos.length === 0) return '0.0';
        const total = videos.reduce((sum, video) => sum + (video.analysis?.overall_score || 0), 0);
        return (total / videos.length).toFixed(1);
    }

    showApprovedVideos(videos) {
        const container = document.getElementById('approvedVideos');
        
        if (videos.length === 0) {
            container.innerHTML = `
                <div class="text-center py-8">
                    <i class="fas fa-info-circle text-gray-400 text-4xl mb-4"></i>
                    <h3 class="text-lg font-semibold text-gray-600">No Videos Approved</h3>
                    <p class="text-gray-500">No videos met the minimum quality standards.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <h3 class="text-lg font-semibold text-gray-900 mb-4">
                <i class="fas fa-trophy text-yellow-500 mr-2"></i>
                Approved Videos (${videos.length})
            </h3>
            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                ${videos.map(video => this.createVideoCard(video)).join('')}
            </div>
        `;
    }

    createVideoCard(video) {
        const analysis = video.analysis || {};
        const foodItems = analysis.food_items || [];
        const score = analysis.overall_score || 0;
        
        return `
            <div class="video-card bg-white border border-gray-200 rounded-xl p-4">
                <div class="flex justify-between items-start mb-3">
                    <div class="flex-1">
                        <h4 class="font-semibold text-gray-900">Video ${video.shortcode}</h4>
                        <p class="text-sm text-gray-600">${foodItems.slice(0, 2).join(', ')}</p>
                    </div>
                    <div class="bg-green-100 px-3 py-1 rounded-full">
                        <span class="text-green-800 font-semibold text-sm">${score.toFixed(1)}/10</span>
                    </div>
                </div>
                
                <div class="space-y-2 mb-4">
                    ${this.createScoreBar('Food Quality', analysis.food_quality || 0)}
                    ${this.createScoreBar('Visual Appeal', analysis.visual_appeal || 0)}
                    ${this.createScoreBar('Professionalism', analysis.professionalism || 0)}
                </div>
                
                <a href="${video.original_url}" target="_blank" 
                   class="inline-flex items-center text-blue-600 hover:text-blue-800 font-medium">
                    <i class="fab fa-instagram mr-2"></i>
                    View on Instagram
                    <i class="fas fa-external-link-alt ml-1 text-xs"></i>
                </a>
            </div>
        `;
    }

    createScoreBar(label, score) {
        const percentage = (score / 10) * 100;
        const colorClass = score >= 7 ? 'bg-green-500' : score >= 5 ? 'bg-yellow-500' : 'bg-red-500';
        
        return `
            <div class="flex items-center text-xs">
                <span class="w-16 text-gray-600">${label}</span>
                <div class="flex-1 bg-gray-200 rounded-full h-2 mx-2">
                    <div class="${colorClass} h-2 rounded-full" style="width: ${percentage}%"></div>
                </div>
                <span class="text-gray-700 font-medium">${score.toFixed(1)}</span>
            </div>
        `;
    }

    showSMSPreview(smsPreview) {
        const container = document.getElementById('smsContent');
        
        if (typeof smsPreview === 'string') {
            // Legacy single message format
            container.textContent = smsPreview;
        } else if (smsPreview && smsPreview.total_messages) {
            // New two-part message format
            let html = '';
            
            if (smsPreview.total_messages === 2) {
                html = `
                    <div class="space-y-4">
                        <div class="bg-blue-50 border border-blue-200 rounded-lg p-3">
                            <div class="flex items-center mb-2">
                                <i class="fas fa-mobile-alt text-blue-500 mr-2"></i>
                                <span class="font-semibold text-blue-700">SMS 1/2</span>
                                <span class="ml-auto text-xs text-blue-600">${smsPreview.message_1.length} chars</span>
                            </div>
                            <div class="text-sm text-gray-800 whitespace-pre-wrap">${smsPreview.message_1}</div>
                        </div>
                        
                        <div class="bg-green-50 border border-green-200 rounded-lg p-3">
                            <div class="flex items-center mb-2">
                                <i class="fas fa-mobile-alt text-green-500 mr-2"></i>
                                <span class="font-semibold text-green-700">SMS 2/2</span>
                                <span class="ml-auto text-xs text-green-600">${smsPreview.message_2.length} chars</span>
                            </div>
                            <div class="text-sm text-gray-800 whitespace-pre-wrap">${smsPreview.message_2}</div>
                        </div>
                    </div>
                `;
            } else {
                html = `<div class="text-sm text-gray-800 whitespace-pre-wrap">${smsPreview.message_1}</div>`;
            }
            
            container.innerHTML = html;
        } else {
            container.textContent = 'No SMS preview available';
        }
    }

    sendSMS() {
        if (!this.currentResults) return;
        
        const button = document.getElementById('sendSmsBtn');
        const originalText = button.innerHTML;
        
        // Show loading state
        button.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Sending...';
        button.disabled = true;
        
        fetch('/send_sms', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                phone: this.currentResults.phone,
                restaurant_name: this.currentResults.restaurant_name,
                approved_videos: this.currentResults.approved_videos || []
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.error) {
                this.showModal('error', 'SMS Error', data.error);
            } else {
                this.showModal('success', 'SMS Sent!', 'The message has been sent to the restaurant successfully.');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            this.showModal('error', 'Error', 'Failed to send SMS. Please try again.');
        })
        .finally(() => {
            // Restore button
            button.innerHTML = originalText;
            button.disabled = false;
        });
    }

    clearProgress() {
        document.getElementById('progressSteps').innerHTML = '';
        document.getElementById('progressPercent').textContent = '0%';
        document.getElementById('progressBar').style.width = '0%';
    }

    toggleForm(enabled) {
        const form = document.getElementById('restaurantForm');
        const inputs = form.querySelectorAll('input, select, button');
        inputs.forEach(input => input.disabled = !enabled);
        
        const button = document.getElementById('analyzeBtn');
        if (enabled) {
            button.innerHTML = '<i class="fas fa-play mr-2"></i>Start Analysis';
        } else {
            button.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Processing...';
        }
    }

    showModal(type, title, message) {
        const modal = document.getElementById('notificationModal');
        const icon = document.getElementById('notificationIcon');
        const titleEl = document.getElementById('notificationTitle');
        const messageEl = document.getElementById('notificationMessage');
        
        if (type === 'success') {
            icon.innerHTML = '<i class="fas fa-check-circle text-green-500"></i>';
        } else {
            icon.innerHTML = '<i class="fas fa-exclamation-triangle text-red-500"></i>';
        }
        
        titleEl.textContent = title;
        messageEl.textContent = message;
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }

    hideModal() {
        const modal = document.getElementById('notificationModal');
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

// Initialize the app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new RestaurantAnalyzer();
});