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
        // 플러스 버튼 이벤트 바인딩
        setTimeout(() => {
            const newBtn = document.getElementById('new-session-btn');
            if (newBtn) {
                newBtn.addEventListener('click', async () => {
                    await this.startNewSession();
                    await this.loadSession(this.currentSessionId);
                });
            }
        }, 0);
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

        // Enter로 메시지 전송, Shift+Enter는 줄바꿈
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
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

        // Session selection & 삭제 이벤트 위임
        document.addEventListener('click', (e) => {
            // 삭제 버튼 클릭
            if (e.target.classList.contains('session-delete-btn')) {
                e.stopPropagation();
                const sessionId = e.target.dataset.sessionId;
                if (confirm('이 채팅방을 삭제하시겠습니까?')) {
                    this.deleteSession(sessionId);
                }
                return;
            }
            // 채팅방 선택
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
                    <button class="chart-btn" data-action="sql" data-sql='${JSON.stringify(metadata.sql_results)}' disabled>SQL</button>
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
        
        // LLM 추천 설정을 로그로 확인
        console.log('[DEBUG] LLM 추천 시각화 설정:', viz);
        console.log('[DEBUG] 데이터 샘플:', data.slice(0, 3));

        try {
            let plotlyData = [];
            let layout = {
                title: {
                    text: viz.title || '분석 결과',
                    font: { color: '#f8fafc', size: 22 },
                    x: 0.5
                },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#f8fafc', size: 18 },
                xaxis: { 
                    title: { text: viz.xAxis || 'X축', font: { size: 18, color: '#f8fafc' } },
                    showgrid: false,
                    color: '#f8fafc',
                    tickfont: { size: 15, color: '#f8fafc' }
                },
                yaxis: { 
                    title: { text: viz.yAxis || 'Y축', font: { size: 18, color: '#f8fafc' } },
                    showgrid: false,
                    color: '#f8fafc',
                    tickfont: { size: 15, color: '#f8fafc' }
                },
                legend: { font: { size: 16, color: '#f8fafc' } },
                margin: { t: 60, r: 50, b: 60, l: 60 }
            };

            // 데이터 컬럼 확인 및 매핑
            const availableColumns = Object.keys(data[0] || {});
            console.log('[DEBUG] 사용 가능한 컬럼들:', availableColumns);
            
            // LLM이 추천한 컬럼명이 실제 데이터에 있는지 확인
            const xColumn = availableColumns.find(col => 
                col === viz.xAxis || 
                col.toLowerCase().includes(viz.xAxis?.toLowerCase()) ||
                viz.xAxis?.toLowerCase().includes(col.toLowerCase())
            ) || availableColumns[0];
            
            const yColumn = availableColumns.find(col => 
                col === viz.yAxis || 
                col.toLowerCase().includes(viz.yAxis?.toLowerCase()) ||
                viz.yAxis?.toLowerCase().includes(col.toLowerCase())
            ) || availableColumns[1];
            
            const seriesColumn = viz.seriesBy && viz.seriesBy !== 'null' && viz.seriesBy !== null && viz.seriesBy !== 'None' ? 
                availableColumns.find(col => 
                    col === viz.seriesBy || 
                    col.toLowerCase().includes(viz.seriesBy?.toLowerCase()) ||
                    viz.seriesBy?.toLowerCase().includes(col.toLowerCase())
                ) : null;

            console.log('[DEBUG] 매핑된 컬럼들:', { xColumn, yColumn, seriesColumn });

            // 차트 타입에 따른 처리
            switch (viz.chartType?.toLowerCase()) {
                case 'bar':
                    plotlyData = this.createBarChart(data, xColumn, yColumn, seriesColumn);
                    break;
                case 'line':
                    plotlyData = this.createLineChart(data, xColumn, yColumn, seriesColumn);
                    break;
                case 'pie':
                    plotlyData = this.createPieChart(data, xColumn, yColumn);
                    layout.showlegend = true;
                    break;
                case 'scatter':
                    plotlyData = this.createScatterChart(data, xColumn, yColumn, seriesColumn);
                    break;
                case 'heatmap':
                    plotlyData = this.createHeatmapChart(data, xColumn, yColumn, seriesColumn);
                    break;
                default:
                    // 기본값: bar 차트
                    console.log('[DEBUG] 지원하지 않는 차트 타입, bar 차트로 대체:', viz.chartType);
                    plotlyData = this.createBarChart(data, xColumn, yColumn, seriesColumn);
            }

            // 축 레이블 업데이트
            layout.xaxis.title = viz.xAxis || xColumn || 'X축';
            layout.yaxis.title = viz.yAxis || yColumn || 'Y축';

            console.log('[DEBUG] 최종 Plotly 데이터:', plotlyData);
            console.log('[DEBUG] 최종 Layout:', layout);

            Plotly.newPlot(chartId, plotlyData, layout, {
                responsive: true,
                displayModeBar: false
            });

        } catch (error) {
            console.error('[ERROR] 차트 렌더링 오류:', error);
            document.getElementById(chartId).innerHTML = '<p style="color: #ef4444;">차트 렌더링 오류가 발생했습니다.</p>';
        }
    }

    // 막대 차트 생성
    createBarChart(data, xColumn, yColumn, seriesColumn) {
        if (seriesColumn) {
            // 시리즈별 그룹화
            const seriesGroups = [...new Set(data.map(d => d[seriesColumn]))];
            const xValues = [...new Set(data.map(d => d[xColumn]))];
            
            return seriesGroups.map(series => ({
                x: xValues,
                y: xValues.map(x => {
                    const found = data.find(d => d[xColumn] == x && d[seriesColumn] == series);
                    return found ? parseFloat(found[yColumn]) || 0 : 0;
                }),
                name: series,
                type: 'bar',
                marker: { opacity: 0.8 }
            }));
        } else {
            // 단일 시리즈
            return [{
                x: data.map(d => d[xColumn]),
                y: data.map(d => parseFloat(d[yColumn]) || 0),
                type: 'bar',
                marker: { color: '#3b82f6', opacity: 0.8 }
            }];
        }
    }

    // 선 차트 생성
    createLineChart(data, xColumn, yColumn, seriesColumn) {
        if (seriesColumn) {
            // 시리즈별 그룹화
            const seriesGroups = [...new Set(data.map(d => d[seriesColumn]))];
            const xValues = [...new Set(data.map(d => d[xColumn]))].sort();
            
            return seriesGroups.map(series => ({
                x: xValues,
                y: xValues.map(x => {
                    const found = data.find(d => d[xColumn] == x && d[seriesColumn] == series);
                    return found ? parseFloat(found[yColumn]) || 0 : 0;
                }),
                name: series,
                type: 'scatter',
                mode: 'lines+markers',
                line: { width: 3 },
                marker: { size: 8 }
            }));
        } else {
            // 단일 시리즈
            return [{
                x: data.map(d => d[xColumn]),
                y: data.map(d => parseFloat(d[yColumn]) || 0),
                type: 'scatter',
                mode: 'lines+markers',
                line: { color: '#3b82f6', width: 3 },
                marker: { color: '#3b82f6', size: 8 }
            }];
        }
    }

    // 파이 차트 생성
    createPieChart(data, xColumn, yColumn) {
        return [{
            labels: data.map(d => d[xColumn]),
            values: data.map(d => parseFloat(d[yColumn]) || 0),
            type: 'pie',
            textinfo: 'label+percent',
            textfont: { color: '#f8fafc' },
            marker: {
                colors: ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4', '#84cc16']
            }
        }];
    }

    // 산점도 차트 생성
    createScatterChart(data, xColumn, yColumn, seriesColumn) {
        if (seriesColumn) {
            // 시리즈별 그룹화
            const seriesGroups = [...new Set(data.map(d => d[seriesColumn]))];
            
            return seriesGroups.map(series => ({
                x: data.filter(d => d[seriesColumn] == series).map(d => parseFloat(d[xColumn]) || 0),
                y: data.filter(d => d[seriesColumn] == series).map(d => parseFloat(d[yColumn]) || 0),
                name: series,
                type: 'scatter',
                mode: 'markers',
                marker: { size: 10, opacity: 0.7 }
            }));
        } else {
            // 단일 시리즈
            return [{
                x: data.map(d => parseFloat(d[xColumn]) || 0),
                y: data.map(d => parseFloat(d[yColumn]) || 0),
                type: 'scatter',
                mode: 'markers',
                marker: { color: '#3b82f6', size: 10, opacity: 0.7 }
            }];
        }
    }

    // 히트맵 차트 생성
    createHeatmapChart(data, xColumn, yColumn, valueColumn) {
        // 히트맵은 x, y 축과 값(z)이 필요
        const xValues = [...new Set(data.map(d => d[xColumn]))];
        const yValues = [...new Set(data.map(d => d[yColumn]))];
        const zColumn = valueColumn || Object.keys(data[0]).find(k => k !== xColumn && k !== yColumn);
        
        const z = yValues.map(y => 
            xValues.map(x => {
                const found = data.find(d => d[xColumn] == x && d[yColumn] == y);
                return found ? parseFloat(found[zColumn]) || 0 : 0;
            })
        );

        return [{
            x: xValues,
            y: yValues,
            z: z,
            type: 'heatmap',
            colorscale: 'Blues',
            showscale: true
        }];
    }

    handleChartAction(button) {
        const action = button.dataset.action;
        if (action === 'sql') {
            let sqlData = [];
            try {
                sqlData = JSON.parse(button.dataset.sql);
                if (!Array.isArray(sqlData)) sqlData = [];
            } catch (e) {
                sqlData = [];
            }
            this.showSQLModal(sqlData);
        } else if (action === 'copy') {
                this.copyChart(button);
        } else if (action === 'data' || action === 'feedback') {
                this.showInfo('해당 기능은 준비 중입니다.');
        }
    }

    showSQLModal(sqlResults) {
        // 모달 중복 방지
        if (document.querySelector('.sql-modal')) {
            document.querySelector('.sql-modal').remove();
        }
        const modal = document.createElement('div');
        modal.className = 'sql-modal';
        // 쿼리 텍스트만 추출 (여러 개면 모두 합침)
        let allSqlText = '';
        if (Array.isArray(sqlResults) && sqlResults.length > 0) {
            allSqlText = sqlResults.map(result => result.query).join('\n\n');
        }
        modal.innerHTML = `
            <div class="sql-modal-content">
                <div class="sql-modal-header">
                    <h3 class="sql-modal-title">생성된 SQL 쿼리</h3>
                    <div style="display: flex; gap: 1rem; align-items: center;">
                        <button class="copy-sql-btn" style="padding: 0.5rem 1.2rem; font-size: 1rem; background: var(--accent-blue); color: white; border: none; border-radius: 0.375rem; cursor: pointer;">복사</button>
                    <button class="close-btn">&times;</button>
                    </div>
                </div>
                <div class="sql-content">
                    ${Array.isArray(sqlResults) && sqlResults.length > 0 ? sqlResults.map(result => `
                        <h4>${result.description || ''}</h4>
                        <pre>${result.query || ''}</pre>
                        ${result.error ? `<p style=\"color: #ef4444;\">오류: ${result.error}</p>` : ''}
                    `).join('\n\n') : '<p style="color: #ef4444;">SQL 쿼리 정보가 없습니다.</p>'}
                </div>
            </div>
        `;
        document.body.appendChild(modal);
        // 복사 버튼 이벤트
        modal.querySelector('.copy-sql-btn').addEventListener('click', () => {
            if (allSqlText) {
                navigator.clipboard.writeText(allSqlText).then(() => {
                    alert('SQL 쿼리가 복사되었습니다!');
                });
            } else {
                alert('복사할 SQL 쿼리 정보가 없습니다.');
            }
        });
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

        const metricName = element.textContent;
        try {
            const response = await fetch('/api/select_metric', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.currentSessionId,
                    metric: metricName
                })
            });

            if (!response.ok) {
                throw new Error('Failed to select metric');
            }

            const data = await response.json();
            if (data.panels_active) {
                // 차트 패널과 채팅 패널 활성화
                document.querySelector('.center-panel').classList.add('active');
                document.querySelector('.right-panel').classList.add('active');
                
                // 채팅 입력창 활성화 및 포커스
                const chatInput = document.getElementById('chat-input');
                chatInput.disabled = false;
                chatInput.placeholder = `${metricName}에 대해 궁금한 점을 물어보세요...`;
                chatInput.focus();
                
                // 품질부적합 선택 시 상단영역1과 상단영역2에 차트 생성
                if (metricName === '품질부적합') {
                    this.createTopAreaChart();
                    this.createTopArea2Chart();
                }
                
                // 성공 메시지 표시
                this.showSuccess(`${metricName} 분석이 시작되었습니다.`);
            }

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
            const currentId = this.currentSessionId;
            container.innerHTML = sessions.map(session => `
                <li class="session-item${session.session_id === currentId ? ' active' : ''}" data-session-id="${session.session_id}">
                    <span class="session-title">${session.title}</span>
                    <span class="session-status ${session.session_id === currentId ? 'active' : 'inactive'}"></span>
                    <button class="session-delete-btn" title="채팅방 삭제" data-session-id="${session.session_id}">&#128465;</button>
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

            // 채팅방 리스트 active 상태 즉시 반영
            await this.loadSessions();

        } catch (error) {
            console.error('Error loading session:', error);
            this.showError('세션을 불러올 수 없습니다.');
        }
    }

    async deleteSession(sessionId) {
        try {
            const response = await fetch('/api/delete_session', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ session_id: sessionId })
            });
            if (!response.ok) throw new Error('삭제 실패');
            // 삭제 후 리스트 갱신
            await this.loadSessions();
            // 현재 삭제한 세션이 선택된 세션이면, 아무것도 선택 안 함
            if (this.currentSessionId === sessionId) {
                this.currentSessionId = null;
                document.getElementById('chat-messages').innerHTML = '';
            }
            this.showSuccess('채팅방이 삭제되었습니다.');
        } catch (error) {
            this.showError('채팅방 삭제 중 오류 발생');
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

    async createTopAreaChart() {
        try {
            // 연도별 품질부적합률 데이터 요청
            const response = await fetch('/api/yearly_quality_data', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.currentSessionId
                })
            });

            if (!response.ok) {
                throw new Error('Failed to fetch yearly quality data');
            }

            const data = await response.json();
            
            // 상단영역1에 차트 생성
            const topArea1 = document.querySelector('.top-area-1');
            topArea1.innerHTML = '<div id="top-chart-1" style="width: 100%; height: 100%;"></div>';
            
            // 연도별 색상 설정 (2024년: 빨간색, 2025년: 파란색)
            const colors = data.years.map(year => {
                return year === '2024' ? '#ef4444' : '#3b82f6'; // 빨간색 : 파란색
            });
            
            const borderColors = data.years.map(year => {
                return year === '2024' ? '#dc2626' : '#1e40af'; // 어두운 빨간색 : 어두운 파란색
            });

            // Plotly 차트 생성
            const chartData = [{
                x: data.years,
                y: data.quality_rates,
                type: 'bar',
                marker: {
                    color: colors,
                    line: {
                        color: borderColors,
                        width: 1
                    }
                },
                text: data.quality_rates.map(rate => `${rate.toFixed(2)}%`),
                textposition: 'auto',
                hovertemplate: '<b>%{x}년</b><br>품질부적합률: %{y:.2f}%<extra></extra>'
            }];

            const layout = {
                title: {
                    text: '연도별 품질부적합률',
                    font: { color: '#f8fafc', size: 16 },
                    x: 0.5
                },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#f8fafc' },
                xaxis: {
                    title: '연도',
                    showgrid: false,
                    tickcolor: '#6b7280',
                    linecolor: '#6b7280'
                },
                yaxis: {
                    title: '품질부적합률 (%)',
                    showgrid: false,
                    tickcolor: '#6b7280',
                    linecolor: '#6b7280'
                },
                margin: { t: 50, r: 30, b: 50, l: 60 }
            };

            const config = {
                responsive: true,
                displayModeBar: false
            };

            Plotly.newPlot('top-chart-1', chartData, layout, config);

        } catch (error) {
            console.error('Error creating top area chart:', error);
            const topArea1 = document.querySelector('.top-area-1');
            topArea1.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #ef4444;">차트 로딩 중 오류가 발생했습니다.</div>';
        }
    }

    async createTopArea2Chart() {
        try {
            // 2025년 1월~3월 월별 품질부적합률 추세 데이터 요청
            const response = await fetch('/api/monthly_quality_trend', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    session_id: this.currentSessionId
                })
            });

            if (!response.ok) {
                throw new Error('Failed to fetch monthly quality trend data');
            }

            const data = await response.json();
            
            // 상단영역2에 차트 생성
            const topArea2 = document.querySelector('.top-area-2');
            topArea2.innerHTML = '<div id="top-chart-2" style="width: 100%; height: 100%;"></div>';

            // Plotly 꺾은선 차트 생성
            const chartData = [{
                x: data.months,
                y: data.quality_rates,
                type: 'scatter',
                mode: 'lines+markers',
                line: {
                    color: '#3b82f6', // 2025년 막대그래프와 동일한 파란색
                    width: 3
                },
                marker: {
                    color: '#1e40af', // 진한 파란색 꼭지점
                    size: 8,
                    line: {
                        color: '#1e3a8a', // 더 진한 파란색 테두리
                        width: 2
                    }
                },
                hovertemplate: '<b>2025년 %{x}</b><br>품질부적합률: %{y:.2f}%<extra></extra>'
            }];

            const layout = {
                title: {
                    text: '2025년 품질부적합률 추이',
                    font: { color: '#f8fafc', size: 16 },
                    x: 0.5
                },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#f8fafc' },
                xaxis: {
                    title: '월',
                    showgrid: false,
                    tickcolor: '#6b7280',
                    linecolor: '#6b7280'
                },
                yaxis: {
                    title: '품질부적합률 (%)',
                    showgrid: false,
                    tickcolor: '#6b7280',
                    linecolor: '#6b7280'
                },
                margin: { t: 50, r: 30, b: 50, l: 60 }
            };

            const config = {
                responsive: true,
                displayModeBar: false
            };

            Plotly.newPlot('top-chart-2', chartData, layout, config);

        } catch (error) {
            console.error('Error creating top area 2 chart:', error);
            const topArea2 = document.querySelector('.top-area-2');
            topArea2.innerHTML = '<div style="display: flex; align-items: center; justify-content: center; height: 100%; color: #ef4444;">차트 로딩 중 오류가 발생했습니다.</div>';
        }
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
