
class TestAutomation {
  constructor() {
    this.isRunning = false;
    this.currentStep = 0;
    this.startTime = null;
    this.timerInterval = null;
    this.steps = [
      { title: "Environment Setup", description: "테스트 환경 초기화 및 설정", duration: 2000 },
      { title: "Dependency Check", description: "필수 종속성 및 라이브러리 확인", duration: 1500 },
      { title: "Unit Tests", description: "개별 모듈 및 함수 단위 테스트", duration: 3000 },
      { title: "Integration Tests", description: "모듈 간 통합 테스트 실행", duration: 4000 },
      { title: "API Tests", description: "API 엔드포인트 및 응답 검증", duration: 2500 },
      { title: "Performance Tests", description: "성능 및 부하 테스트 수행", duration: 3500 },
      { title: "Security Scan", description: "보안 취약점 스캔 및 검증", duration: 3000 },
      { title: "Report Generation", description: "테스트 결과 리포트 생성", duration: 2000 }
    ];
    this.init();
  }

  init() {
    this.bindEvents();
  }

  bindEvents() {
    const testTab = document.getElementById('test-tab');
    const startBtn = document.getElementById('test-start-btn');
    const resetBtn = document.getElementById('test-reset-btn');
    
    if (testTab) {
      testTab.addEventListener('click', (e) => {
        e.preventDefault();
        this.showTestContent();
      });
    }

    if (startBtn) {
      startBtn.addEventListener('click', () => {
        this.startAutomation();
      });
    }

    if (resetBtn) {
      resetBtn.addEventListener('click', () => {
        this.resetAutomation();
      });
    }
  }

  showTestContent() {
    const otherContent = document.querySelector('.qc-panel');
    const cardsContainer = document.querySelector('.cards-container');
    const aiQcContent = document.getElementById('ai-qc-content');
    
    if (otherContent) otherContent.style.display = 'none';
    if (cardsContainer) cardsContainer.style.display = 'none';
    if (aiQcContent) aiQcContent.style.display = 'none';

    const testContent = document.getElementById('test-automation-content');
    if (testContent) {
      testContent.style.display = 'flex';
      this.initializePipeline();
    }
  }

  initializePipeline() {
    const pipelineFlow = document.getElementById('test-pipeline-flow');
    if (!pipelineFlow) return;
    
    pipelineFlow.innerHTML = '';
    this.showNextStep(0);
  }

  showNextStep(stepIndex) {
    const pipelineFlow = document.getElementById('test-pipeline-flow');
    if (!pipelineFlow || stepIndex >= this.steps.length) return;
    
    const existingStep = document.getElementById(`pipeline-step-${stepIndex}`);
    if (existingStep) return;
    
    const step = this.steps[stepIndex];
    const pipelineStep = document.createElement('div');
    pipelineStep.className = 'pipeline-step';
    pipelineStep.id = `pipeline-step-${stepIndex}`;
    pipelineStep.innerHTML = `
      <div class="step-marker">
        <div class="step-dot">
          <div class="step-spinner"></div>
          <div class="step-check">✓</div>
        </div>
        <div class="step-line"></div>
      </div>
      <div class="step-content">
        <div class="step-title">${step.title}</div>
        <div class="step-description">${step.description}</div>
        <div class="step-status">대기 중</div>
      </div>
    `;
    
    pipelineFlow.appendChild(pipelineStep);
    
    setTimeout(() => {
      pipelineStep.classList.add('visible');
    }, 150);
  }

  async startAutomation() {
    if (this.isRunning) return;

    this.isRunning = true;
    this.currentStep = 0;
    this.startTime = Date.now();
    
    this.updateStatus();
    this.startTimer();
    
    for (let i = 0; i < this.steps.length; i++) {
      await this.executeStep(i);
    }
    
    this.completeAutomation();
  }

  async executeStep(stepIndex) {
    const step = this.steps[stepIndex];
    this.currentStep = stepIndex + 1;
    
    const pipelineStep = document.getElementById(`pipeline-step-${stepIndex}`);
    if (pipelineStep) {
      pipelineStep.className = 'pipeline-step running visible';
      const status = pipelineStep.querySelector('.step-status');
      if (status) status.textContent = '실행 중...';
    }
    
    this.updateStatus();
    await this.addTerminalLogs(step, stepIndex);
    
    if (pipelineStep) {
      pipelineStep.className = 'pipeline-step completed visible';
      const status = pipelineStep.querySelector('.step-status');
      if (status) status.textContent = '완료';
    }
    
    if (stepIndex + 1 < this.steps.length) {
      setTimeout(() => {
        this.showNextStep(stepIndex + 1);
      }, 500);
    }
  }

  async addTerminalLogs(step, stepIndex) {
    const terminalContent = document.getElementById('test-terminal-content');
    if (!terminalContent) return;

    if (stepIndex === 0) {
      terminalContent.innerHTML = '';
    }

    const timestamp = new Date().toTimeString().split(' ')[0];
    const logs = [
      `[${timestamp}] Starting ${step.title}...`,
      `[${timestamp}] ${step.description}`,
      `[${timestamp}] Executing test procedures...`
    ];

    for (const log of logs) {
      const logElement = document.createElement('div');
      logElement.textContent = log;
      logElement.style.color = 'var(--ink-2)';
      logElement.style.marginBottom = '4px';
      terminalContent.appendChild(logElement);
      
      await this.delay(300);
    }

    await this.delay(step.duration - 900);
    const completeLog = document.createElement('div');
    completeLog.textContent = `[${new Date().toTimeString().split(' ')[0]}] ${step.title} completed successfully ✓`;
    completeLog.style.color = '#10b981';
    completeLog.style.marginBottom = '8px';
    terminalContent.appendChild(completeLog);
    
    terminalContent.scrollTop = terminalContent.scrollHeight;
  }

  completeAutomation() {
    this.isRunning = false;
    this.updateStatus();
    this.stopTimer();
    
    if (typeof toastManager !== 'undefined') {
      toastManager.show('테스트 자동화가 성공적으로 완료되었습니다.', 'success', 'Test 완료');
    }
  }

  resetAutomation() {
    if (this.isRunning) return;
    
    this.isRunning = false;
    this.currentStep = 0;
    this.startTime = null;
    this.stopTimer();
    
    this.resetStatus();
    this.initializePipeline();
    
    const terminalContent = document.getElementById('test-terminal-content');
    if (terminalContent) {
      terminalContent.innerHTML = `
        <div class="terminal-welcome">
          <p>Test automation terminal ready...</p>
          <p>Click "Start Test Suite" to begin execution</p>
        </div>
      `;
    }
  }

  updateStatus() {
    const progressValue = document.getElementById('test-progress-value');
    const stepsValue = document.getElementById('test-steps-value');
    const durationValue = document.getElementById('test-duration-value');
    const performanceValue = document.getElementById('test-performance-value');
    
    if (progressValue) {
      const progress = this.currentStep === 0 ? 0 : Math.round((this.currentStep / this.steps.length) * 100);
      progressValue.textContent = `${progress}%`;
    }
    
    if (stepsValue) {
      stepsValue.textContent = `${this.currentStep}/${this.steps.length}`;
    }
    
    if (durationValue && this.startTime) {
      const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
      const minutes = Math.floor(elapsed / 60);
      const seconds = elapsed % 60;
      durationValue.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
    
    if (performanceValue) {
      if (this.currentStep === 0) {
        performanceValue.textContent = '--';
      } else {
        const performance = Math.floor(Math.random() * 30) + 85; // 85-115 범위
        performanceValue.textContent = `${performance}%`;
      }
    }
    
    const pipelineStatus = document.getElementById('pipeline-status');
    if (pipelineStatus) {
      if (this.isRunning) {
        pipelineStatus.textContent = 'Running';
      } else if (this.currentStep === this.steps.length) {
        pipelineStatus.textContent = 'Completed';
      } else {
        pipelineStatus.textContent = 'Ready';
      }
    }
    
    const statusIndicator = document.getElementById('test-status-indicator');
    if (statusIndicator) {
      const dot = statusIndicator.querySelector('.status-dot');
      const span = statusIndicator.querySelector('span');
      
      if (this.isRunning) {
        if (dot) dot.className = 'status-dot running';
        if (span) span.textContent = 'Executing Tests';
      } else if (this.currentStep === this.steps.length) {
        if (dot) dot.className = 'status-dot completed';
        if (span) span.textContent = 'Tests Completed';
      } else {
        if (dot) dot.className = 'status-dot ready';
        if (span) span.textContent = 'Ready to Execute';
      }
    }
  }

  resetStatus() {
    const progressValue = document.getElementById('test-progress-value');
    const stepsValue = document.getElementById('test-steps-value');
    const durationValue = document.getElementById('test-duration-value');
    const performanceValue = document.getElementById('test-performance-value');
    
    if (progressValue) progressValue.textContent = '0%';
    if (stepsValue) stepsValue.textContent = '0/8';
    if (durationValue) durationValue.textContent = '00:00';
    if (performanceValue) performanceValue.textContent = '--';
    
    const pipelineFlow = document.getElementById('test-pipeline-flow');
    if (pipelineFlow) pipelineFlow.innerHTML = '';
  }

  startTimer() {
    this.timerInterval = setInterval(() => {
      this.updateStatus();
    }, 1000);
  }

  stopTimer() {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
  }

  delay(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
}


document.addEventListener('DOMContentLoaded', () => {
  window.testAutomation = new TestAutomation();
});

if (document.readyState !== 'loading') {
  window.testAutomation = new TestAutomation();
}