class QualityAnalysisApp {
    constructor() {
        this.currentSessionId = null;
        this.isLoading = false;
        this.init();
    }

    async init() {
        this.bindEvents();
        await this.startNewSession();
        await this.loadSessions();
        this.setupChartContainer();
    }

    bindEvents() {
        // Chat form submission
        const chatForm = document.getElementById('chat-form');
        const chatInput = document.getElementById('chat-input');
        const sendBtn = document.getElementById('send-btn');

        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            this.sendMessage();
        });

        // Auto-resize textarea
        chatInput.addEventListener('input', () => {
            chatInput.style.height = 'auto';
            chatInput.style.height = chatInput.scrollHeight + 'px';
        });

        // Reset button
        document.getElementById('reset-btn').addEventListener('click', () => {
            this.resetSession();
        });

        // Metric selection
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('metric-button')) {
                this.toggleMetricDropdown(e.target);
            }
            if (e.target.classList.contains('sub-metric')) {
                this.selectMetric(e.target);
            }
        });

        // Session selection
        document.addEventListener('click', (e) => {
            if (e.target.closest('.session-item')) {
                const sessionId = e.target.closest('.session-item').dataset.sessionId;
                this.loadSession(sessionId);
            }
        });

        // Modal close
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('sql-modal') || e.target.classList.contains('close-btn')) {
                this.closeSQLModal();
            }
        });

        // Chart button actions
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('chart-btn')) {
                this.handleChartAction(e.target);
            }
        });
    }

    async startNewSession() {
        try {
            const response = await fetch('/api/start_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });

            if (!response.ok) {
                throw new Error('Failed to start session');
            }

            const data = await response.json();
            this.currentSessionId = data.session_id;
            console.log('New session started:', this.currentSessionId);

        } catch (error) {
            console.error('Error starting session:', error);
            this.showError('세션을 시작할 수 없습니다.');
        }
    }

    async sendMessage() {
        const input = document.getElementById('chat-input');
        const message = input.value.trim();

        if (!message || this.isLoading) return;

        input.value = '';
        input.style.height = 'auto';
        this.isLoading = true;
        this.updateSendButton(true);

        // Add user message to chat
        this.addMessageToChat('user', message);
        this.showTypingIndicator();

        try {
            const response = await fetch('/api/chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.currentSessionId,
                    message: message
                })
            });

            if (!response.ok) {
                throw new Error('Failed to send message');
            }

            const data = await response.json();
            this.hideTypingIndicator();
            this.handleChatResponse(data);

        } catch (error) {
            console.error('Error sending message:', error);
            this.hideTypingIndicator();
            this.addMessageToChat('assistant', '죄송합니다. 오류가 발생했습니다. 다시 시도해주세요.');
        } finally {
            this.isLoading = false;
            this.updateSendButton(false);
        }
    }

    handleChatResponse(data) {
        // Add assistant message
        this.addMessageToChat('assistant', data.message);

        // Handle different response types
        switch (data.type) {
            case 'analysis':
                if (data.metadata.sql_results && data.metadata.visualization) {
                    this.createChart(data.metadata);
                }
                break;
            case 'confirmation':
                // Handle confirmation dialog if needed
                break;
            case 'error':
                console.error('Chat error:', data.metadata.error);
                break;
        }

        // Update sessions list
        this.loadSessions();
    }

    addMessageToChat(role, content) {
        const messagesContainer = document.getElementById('chat-messages');
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;

        const now = new Date();
        const timeString = now.toLocaleTimeString('ko-KR', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });

        messageDiv.innerHTML = `
            <div class="message-content">${this.formatMessage(content)}</div>
            <div class="message-time">${timeString}</div>
        `;

        messagesContainer.appendChild(messageDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    formatMessage(content) {
        // Basic formatting for messages
        return content
            .replace(/\n/g, '<br>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/\*(.*?)\*/g, '<em>$1</em>');
    }

    showTypingIndicator() {
        const messagesContainer = document.getElementById('chat-messages');
        const typingDiv = document.createElement('div');
        typingDiv.className = 'typing-indicator';
        typingDiv.id = 'typing-indicator';
        typingDiv.innerHTML = `
            <span>LLM이 분석 중입니다</span>
            <div class="typing-dots">
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            </div>
        `;
        messagesContainer.appendChild(typingDiv);
        messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    hideTypingIndicator() {
        const typingIndicator = document.getElementById('typing-indicator');
        if (typingIndicator) {
            typingIndicator.remove();
        }
    }

    updateSendButton(loading) {
        const sendBtn = document.getElementById('send-btn');
        const chatInput = document.getElementById('chat-input');
        
        if (loading) {
            sendBtn.disabled = true;
            sendBtn.innerHTML = '<div class="loading"></div>';
            chatInput.disabled = true;
        } else {
            sendBtn.disabled = false;
            sendBtn.innerHTML = '전송';
            chatInput.disabled = false;
            chatInput.focus();
        }
    }

    setupChartContainer() {
        const container = document.getElementById('charts-container');
        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">📊</div>
                <div class="empty-state-text">시각화 대기 중</div>
                <div class="empty-state-subtext">좌측에서 지표를 선택하거나 우측에서 질문을 입력해주세요</div>
            </div>
        `;
    }

    createChart(metadata) {
        const container = document.getElementById('charts-container');
        
        // Remove empty state if it exists
        const emptyState = container.querySelector('.empty-state');
        if (emptyState) {
            emptyState.remove();
        }

        const chartId = 'chart-' + Date.now();
        const chartDiv = document.createElement('div');
        chartDiv.className = 'chart-item';
        chartDiv.innerHTML = `
            <div class="chart-header">
                <h3 class="chart-title">${metadata.visualization.title || '분석 결과'}</h3>
                <div class="chart-actions">
                    <button class="chart-btn" data-action="sql" data-sql='${JSON.stringify(metadata.sql_results)}'>SQL</button>
                    <button class="chart-btn" data-action="data" disabled>Data</button>
                    <button class="chart-btn" data-action="feedback" disabled>Feedback</button>
                    <button class="chart-btn" data-action="copy">Copy</button>
                </div>
            </div>
            <div class="chart-content" id="${chartId}"></div>
        `;

        container.appendChild(chartDiv);
        this.renderChart(chartId, metadata);
        
        // Scroll to new chart
        chartDiv.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }

    renderChart(chartId, metadata) {
        const { sql_results, visualization } = metadata;
        
        if (!sql_results || sql_results.length === 0 || !sql_results[0].data) {
            document.getElementById(chartId).innerHTML = '<p>데이터가 없습니다.</p>';
            return;
        }

        const data = sql_results[0].data;
        const viz = visualization;

        try {
            let plotlyData = [];
            let layout = {
                title: viz.title || '분석 결과',
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#f8fafc' },
                xaxis: { 
                    title: viz.xAxis,
                    gridcolor: '#475569',
                    color: '#f8fafc'
                },
                yaxis: { 
                    title: viz.yAxis,
                    gridcolor: '#475569',
                    color: '#f8fafc'
                },
                margin: { t: 50, r: 50, b: 50, l: 50 }
            };

            // Prepare data based on chart type
            if (viz.chartType === 'bar') {
                const xData = data.map(d => d[viz.xAxis]);
                const yData = data.map(d => d[viz.yAxis]);
                
                plotlyData = [{
                    x: xData,
                    y: yData,
                    type: 'bar',
                    marker: { color: '#3b82f6' }
                }];
            } else if (viz.chartType === 'line') {
                const xData = data.map(d => d[viz.xAxis]);
                const yData = data.map(d => d[viz.yAxis]);
                
                plotlyData = [{
                    x: xData,
                    y: yData,
                    type: 'scatter',
                    mode: 'lines+markers',
                    line: { color: '#3b82f6' },
                    marker: { color: '#60a5fa' }
                }];
            } else if (viz.chartType === 'pie') {
                const labels = data.map(d => d[viz.xAxis]);
                const values = data.map(d => d[viz.yAxis]);
                
                plotlyData = [{
                    labels: labels,
                    values: values,
                    type: 'pie',
                    textinfo: 'label+percent',
                    textfont: { color: '#f8fafc' }
                }];
            } else {
                // Default to bar chart
                const xData = data.map(d => Object.values(d)[0]);
                const yData = data.map(d => Object.values(d)[1]);
                
                plotlyData = [{
                    x: xData,
                    y: yData,
                    type: 'bar',
                    marker: { color: '#3b82f6' }
                }];
            }

            Plotly.newPlot(chartId, plotlyData, layout, {
                responsive: true,
                displayModeBar: false
            });

        } catch (error) {
            console.error('Chart rendering error:', error);
            document.getElementById(chartId).innerHTML = '<p style="color: #ef4444;">차트 렌더링 오류가 발생했습니다.</p>';
        }
    }

    handleChartAction(button) {
        const action = button.dataset.action;
        
        switch (action) {
            case 'sql':
                this.showSQLModal(JSON.parse(button.dataset.sql));
                break;
            case 'copy':
                this.copyChart(button);
                break;
            case 'data':
            case 'feedback':
                this.showInfo('해당 기능은 준비 중입니다.');
                break;
        }
    }

    showSQLModal(sqlResults) {
        const modal = document.createElement('div');
        modal.className = 'sql-modal';
        modal.innerHTML = `
            <div class="sql-modal-content">
                <div class="sql-modal-header">
                    <h3 class="sql-modal-title">생성된 SQL 쿼리</h3>
                    <button class="close-btn">&times;</button>
                </div>
                <div class="sql-content">
                    ${sqlResults.map(result => `
                        <h4>${result.description}</h4>
                        <pre>${result.query}</pre>
                        ${result.error ? `<p style="color: #ef4444;">오류: ${result.error}</p>` : ''}
                    `).join('\n\n')}
                </div>
            </div>
        `;
        document.body.appendChild(modal);
    }

    closeSQLModal() {
        const modal = document.querySelector('.sql-modal');
        if (modal) {
            modal.remove();
        }
    }

    async copyChart(button) {
        try {
            const chartElement = button.closest('.chart-item').querySelector('.chart-content');
            const canvas = chartElement.querySelector('canvas');
            
            if (canvas) {
                canvas.toBlob((blob) => {
                    const item = new ClipboardItem({ 'image/png': blob });
                    navigator.clipboard.write([item]).then(() => {
                        this.showSuccess('차트가 클립보드에 복사되었습니다.');
                    });
                });
            } else {
                this.showInfo('차트를 복사할 수 없습니다.');
            }
        } catch (error) {
            console.error('Copy error:', error);
            this.showError('복사 중 오류가 발생했습니다.');
        }
    }

    toggleMetricDropdown(button) {
        const dropdown = button.nextElementSibling;
        if (dropdown && dropdown.classList.contains('dropdown-content')) {
            dropdown.classList.toggle('show');
            
            // Close other dropdowns
            document.querySelectorAll('.dropdown-content.show').forEach(d => {
                if (d !== dropdown) d.classList.remove('show');
            });
        }
    }

    async selectMetric(element) {
        if (!element.classList.contains('available')) {
            this.showInfo('해당 지표는 아직 지원되지 않습니다.');
            return;
        }

        const metric = element.textContent.trim();
        
        try {
            const response = await fetch('/api/select_metric', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.currentSessionId,
                    metric: metric
                })
            });

            if (!response.ok) {
                throw new Error('Failed to select metric');
            }

            const data = await response.json();
            this.handleChatResponse(data);

        } catch (error) {
            console.error('Error selecting metric:', error);
            this.showError('지표 선택 중 오류가 발생했습니다.');
        }
    }

    async resetSession() {
        if (!confirm('현재 대화와 차트를 모두 초기화하시겠습니까?')) {
            return;
        }

        try {
            const response = await fetch('/api/reset_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.currentSessionId
                })
            });

            if (!response.ok) {
                throw new Error('Failed to reset session');
            }

            // Clear UI
            document.getElementById('chat-messages').innerHTML = '';
            this.setupChartContainer();
            this.showSuccess('세션이 초기화되었습니다.');

        } catch (error) {
            console.error('Error resetting session:', error);
            this.showError('세션 초기화 중 오류가 발생했습니다.');
        }
    }

    async loadSessions() {
        try {
            const response = await fetch('/api/sessions');
            if (!response.ok) return;

            const sessions = await response.json();
            const container = document.querySelector('.chat-sessions');
            
            container.innerHTML = sessions.map(session => `
                <li class="session-item" data-session-id="${session.session_id}">
                    <div class="session-title">${session.title}</div>
                    <div class="session-meta">${session.message_count}개 메시지 • ${new Date(session.created_at).toLocaleDateString()}</div>
                </li>
            `).join('');

        } catch (error) {
            console.error('Error loading sessions:', error);
        }
    }

    async loadSession(sessionId) {
        try {
            const response = await fetch(`/api/session/${sessionId}`);
            if (!response.ok) return;

            const session = await response.json();
            this.currentSessionId = sessionId;

            // Clear current chat
            const messagesContainer = document.getElementById('chat-messages');
            messagesContainer.innerHTML = '';

            // Load chat history
            session.chat_history.forEach(msg => {
                this.addMessageToChat(msg.role, msg.content);
            });

            this.showInfo('이전 대화를 불러왔습니다.');

        } catch (error) {
            console.error('Error loading session:', error);
            this.showError('세션을 불러올 수 없습니다.');
        }
    }

    showSuccess(message) {
        this.showToast(message, 'success');
    }

    showError(message) {
        this.showToast(message, 'error');
    }

    showInfo(message) {
        this.showToast(message, 'info');
    }

    showToast(message, type) {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 24px;
            border-radius: 6px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            animation: slideIn 0.3s ease;
            background: ${type === 'success' ? '#10b981' : type === 'error' ? '#ef4444' : '#3b82f6'};
        `;

        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 3000);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new QualityAnalysisApp();
});

// Add slide-in animation
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from { transform: translateX(100%); opacity: 0; }
        to { transform: translateX(0); opacity: 1; }
    }
`;
document.head.appendChild(style);
