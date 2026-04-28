
class AIQCAutomation {
  constructor() {
    this.isRunning = false;
    this.currentStep = 0;
    this.startTime = null;
    this.timerInterval = null;
    this.steps = [
      { title: "시스템 초기화", description: "QC 환경 준비 중...", duration: 2000 },
      { title: "서버 연결 확인", description: "대상 서버 연결 상태 점검", duration: 3000 },
      { title: "하드웨어 검사", description: "CPU, RAM, 디스크 상태 분석", duration: 4000 },
      { title: "네트워크 테스트", description: "네트워크 연결 및 속도 측정", duration: 2500 },
      { title: "보안 검증", description: "보안 설정 및 취약점 스캔", duration: 3500 },
      { title: "성능 분석", description: "전체 시스템 성능 평가", duration: 3000 },
      { title: "결과 생성", description: "QC 리포트 작성 완료", duration: 2000 }
    ];
    this.init();
  }

  init() {
    this.bindEvents();
  }

  bindEvents() {
    const aiQcTab = document.getElementById('ai-qc-tab');
    const aiQcStartBtn = document.getElementById('ai-qc-start-btn');
    
    if (aiQcTab) {
      aiQcTab.addEventListener('click', (e) => {
        e.preventDefault();
        this.showAIQCContent();
      });
    }

    if (aiQcStartBtn) {
      aiQcStartBtn.addEventListener('click', () => {
        this.startAutomation();
      });
    }
  }

  showAIQCContent() {
    
    const otherContent = document.querySelector('.qc-panel');
    const cardsContainer = document.querySelector('.cards-container');
    const testContent = document.getElementById('test-automation-content');
    
    if (otherContent) otherContent.style.display = 'none';
    if (cardsContainer) cardsContainer.style.display = 'none';
    if (testContent) testContent.style.display = 'none';

    const aiQcContent = document.getElementById('ai-qc-content');
    if (aiQcContent) {
      aiQcContent.style.display = 'flex';
      this.showWelcomeScreen();
      this.resetTimer();
    }
  }

  hideAIQCContent() {
    const aiQcContent = document.getElementById('ai-qc-content');
    const otherContent = document.querySelector('.qc-panel');
    const cardsContainer = document.querySelector('.cards-container');
    
    if (aiQcContent) aiQcContent.style.display = 'none';
    if (otherContent) otherContent.style.display = 'block';
    if (cardsContainer) cardsContainer.style.display = 'grid';
  }

  showWelcomeScreen() {
    const welcomeScreen = document.getElementById('ai-qc-welcome');
    const logsContainer = document.getElementById('ai-qc-logs');
    const resultsContainer = document.getElementById('ai-qc-results');
    
    if (welcomeScreen) welcomeScreen.style.display = 'flex';
    if (logsContainer) logsContainer.style.display = 'none';
    if (resultsContainer) resultsContainer.style.display = 'none';
  }

  async startAutomation() {
    if (this.isRunning) return;

    this.isRunning = true;
    this.currentStep = 0;
    this.startTime = Date.now();
    
    
    this.showLogsScreen();
    this.startTimer();
    this.updateStatus('실행 중');
    
    
    for (let i = 0; i < this.steps.length; i++) {
      await this.executeStep(i);
    }
    
    
    this.completeAutomation();
  }

  showLogsScreen() {
    const welcomeScreen = document.getElementById('ai-qc-welcome');
    const logsContainer = document.getElementById('ai-qc-logs');
    
    if (welcomeScreen) welcomeScreen.style.display = 'none';
    if (logsContainer) {
      logsContainer.style.display = 'flex';
      logsContainer.innerHTML = '<div class="log-output" style="flex: 1; overflow-y: auto; font-family: Courier New, monospace; font-size: 13px; line-height: 1.5;"></div>';
    }
  }

  async executeStep(stepIndex) {
    const step = this.steps[stepIndex];
    this.currentStep = stepIndex + 1;
    
    
    this.addStepToSidebar(stepIndex);
    
    
    this.addLogEntry(`[${this.formatTime()}] 시작: ${step.title}`);
    this.addLogEntry(`[${this.formatTime()}] ${step.description}`);
    
    
    await this.delay(step.duration);
    
    
    this.addLogEntry(`[${this.formatTime()}] 완료: ${step.title} ✓`);
    this.addLogEntry('');
    
    
    this.completeStepInSidebar(stepIndex);
  }

  addStepToSidebar(stepIndex) {
    const stepsContainer = document.getElementById('ai-qc-steps-container');
    if (!stepsContainer) return;

    const step = this.steps[stepIndex];
    const stepElement = document.createElement('div');
    stepElement.className = 'ai-qc-step running';
    stepElement.id = `ai-qc-step-${stepIndex}`;
    stepElement.innerHTML = `
      <div class="step-indicator">
        <div class="step-number">${stepIndex + 1}</div>
        <div class="step-spinner"></div>
        <div class="step-check">✓</div>
      </div>
      <div class="step-info">
        <div class="step-name">${step.title}</div>
        <div class="step-desc">${step.description}</div>
      </div>
    `;
    
    stepsContainer.appendChild(stepElement);
  }

  completeStepInSidebar(stepIndex) {
    const stepElement = document.getElementById(`ai-qc-step-${stepIndex}`);
    if (stepElement) {
      stepElement.className = 'ai-qc-step completed';
    }
  }

  addLogEntry(message) {
    const logOutput = document.querySelector('.log-output');
    if (!logOutput) return;

    const logLine = document.createElement('div');
    logLine.textContent = message;
    logLine.style.color = 'var(--ink-2)';
    logLine.style.marginBottom = '4px';
    
    logOutput.appendChild(logLine);
    logOutput.scrollTop = logOutput.scrollHeight;
  }

  completeAutomation() {
    this.isRunning = false;
    this.updateStatus('완료');
    this.stopTimer();
    
    
    setTimeout(() => {
      this.showResults();
    }, 1000);

    
    if (typeof toastManager !== 'undefined') {
      toastManager.show('AI QC 자동화가 성공적으로 완료되었습니다.', 'success', 'QC 완료');
    }
  }

  showResults() {
    const resultsContainer = document.getElementById('ai-qc-results');
    const resultsContent = document.getElementById('ai-qc-results-content');
    
    if (resultsContainer && resultsContent) {
      resultsContainer.style.display = 'block';
      resultsContent.innerHTML = `
        <div class="result-summary">
          <div class="result-item success">
            <span class="result-label">총 검사 항목:</span>
            <span class="result-value">${this.steps.length}개</span>
          </div>
          <div class="result-item success">
            <span class="result-label">성공:</span>
            <span class="result-value">${this.steps.length}개</span>
          </div>
          <div class="result-item">
            <span class="result-label">실패:</span>
            <span class="result-value">0개</span>
          </div>
          <div class="result-item">
            <span class="result-label">소요 시간:</span>
            <span class="result-value">${this.getElapsedTime()}</span>
          </div>
        </div>
      `;
    }
  }

  updateStatus(status) {
    const statusText = document.getElementById('ai-qc-status-text');
    if (statusText) {
      statusText.textContent = status;
    }
  }

  startTimer() {
    this.timerInterval = setInterval(() => {
      this.updateTimer();
    }, 1000);
  }

  stopTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }

  resetTimer() {
    this.stopTimer();
    this.startTime = null;
    this.updateTimer();
  }

  updateTimer() {
    const timerDisplay = document.getElementById('ai-qc-timer-display');
    if (!timerDisplay) return;

    if (this.startTime) {
      const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
      const minutes = Math.floor(elapsed / 60);
      const seconds = elapsed % 60;
      timerDisplay.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    } else {
      timerDisplay.textContent = '00:00';
    }
  }

  getElapsedTime() {
    if (this.startTime) {
      const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
      const minutes = Math.floor(elapsed / 60);
      const seconds = elapsed % 60;
      return `${minutes}분 ${seconds}초`;
    }
    return '0분 0초';
  }

  formatTime() {
    const now = new Date();
    return now.toTimeString().split(' ')[0];
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}


document.addEventListener('DOMContentLoaded', () => {
  window.aiQCAutomation = new AIQCAutomation();
});


if (document.readyState !== 'loading') {
  window.aiQCAutomation = new AIQCAutomation();
}