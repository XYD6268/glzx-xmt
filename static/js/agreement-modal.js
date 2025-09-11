/**
 * 协议弹窗管理器
 * 用于在注册和投稿时显示协议弹窗
 */
class AgreementModal {
    constructor() {
        this.modal = null;
        this.agreement = null;
        this.startTime = null;
        this.isAgreed = false;
        this.callback = null;
    }

    /**
     * 检查是否需要显示协议
     * @param {string} type - 协议类型：register 或 upload
     * @param {function} callback - 回调函数
     */
    async checkAndShow(type, callback) {
        this.callback = callback;
        
        try {
            const response = await fetch(`/api/check_agreement/${type}`);
            const data = await response.json();
            
            if (data.required) {
                this.agreement = data.agreement;
                this.showModal();
            } else {
                // 不需要显示协议，直接执行回调
                if (callback) callback(true);
            }
        } catch (error) {
            console.error('检查协议失败:', error);
            // 出错时也执行回调，允许继续操作
            if (callback) callback(true);
        }
    }

    /**
     * 显示协议弹窗
     */
    showModal() {
        if (!this.agreement) return;

        // 创建弹窗HTML
        const modalHTML = `
            <div id="agreementModal" class="agreement-modal-overlay">
                <div class="agreement-modal">
                    <div class="agreement-header">
                        <h2>${this.agreement.title}</h2>
                    </div>
                    <div class="agreement-content">
                        ${this.agreement.content}
                    </div>
                    <div class="agreement-footer">
                        <div class="timer-container">
                            <div class="timer-text">
                                请仔细阅读协议内容，需要阅读 <span id="remainingTime">${this.agreement.min_read_time}</span> 秒后才能同意
                            </div>
                            <div class="timer-progress">
                                <div id="timerProgress" class="timer-progress-bar"></div>
                            </div>
                        </div>
                        <div class="button-container">
                            <button id="disagreeBtn" class="btn btn-secondary">暂不同意</button>
                            <button id="agreeBtn" class="btn btn-primary" disabled>我已阅读并同意</button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // 添加样式
        const style = document.createElement('style');
        style.textContent = `
            .agreement-modal-overlay {
                position: fixed;
                top: 0;
                left: 0;
                width: 100%;
                height: 100%;
                background: rgba(0, 0, 0, 0.8);
                display: flex;
                justify-content: center;
                align-items: center;
                z-index: 10000;
                padding: 20px;
                box-sizing: border-box;
            }
            .agreement-modal {
                background: white;
                border-radius: 12px;
                max-width: 800px;
                width: 100%;
                max-height: 90vh;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3);
                display: flex;
                flex-direction: column;
                overflow: hidden;
            }
            .agreement-header {
                background: #007bff;
                color: white;
                padding: 20px;
                text-align: center;
            }
            .agreement-header h2 {
                margin: 0;
                font-size: 1.5rem;
            }
            .agreement-content {
                padding: 30px;
                overflow-y: auto;
                flex: 1;
                line-height: 1.6;
                color: #333;
            }
            .agreement-content h2,
            .agreement-content h3,
            .agreement-content h4 {
                color: #333;
                margin-top: 20px;
                margin-bottom: 10px;
            }
            .agreement-content p {
                margin-bottom: 15px;
            }
            .agreement-content ul,
            .agreement-content ol {
                margin-bottom: 15px;
                padding-left: 30px;
            }
            .agreement-content li {
                margin-bottom: 5px;
            }
            .agreement-footer {
                padding: 20px;
                background: #f8f9fa;
                border-top: 1px solid #dee2e6;
            }
            .timer-container {
                margin-bottom: 20px;
            }
            .timer-text {
                text-align: center;
                margin-bottom: 10px;
                color: #666;
                font-size: 14px;
            }
            .timer-progress {
                width: 100%;
                height: 8px;
                background: #e9ecef;
                border-radius: 4px;
                overflow: hidden;
            }
            .timer-progress-bar {
                height: 100%;
                background: #007bff;
                width: 0%;
                transition: width 0.1s ease;
            }
            .button-container {
                display: flex;
                justify-content: center;
                gap: 15px;
            }
            .btn {
                padding: 12px 30px;
                border: none;
                border-radius: 6px;
                cursor: pointer;
                font-size: 14px;
                font-weight: bold;
                transition: all 0.2s;
            }
            .btn:disabled {
                opacity: 0.6;
                cursor: not-allowed;
            }
            .btn-primary {
                background: #007bff;
                color: white;
            }
            .btn-primary:hover:not(:disabled) {
                background: #0056b3;
            }
            .btn-secondary {
                background: #6c757d;
                color: white;
            }
            .btn-secondary:hover {
                background: #545b62;
            }
            @media (max-width: 600px) {
                .agreement-modal {
                    margin: 10px;
                    max-height: 95vh;
                }
                .agreement-content {
                    padding: 20px;
                }
                .button-container {
                    flex-direction: column;
                }
            }
        `;
        
        // 添加样式到头部
        document.head.appendChild(style);
        
        // 添加弹窗到页面
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        this.modal = document.getElementById('agreementModal');
        
        // 绑定事件
        this.bindEvents();
        
        // 开始计时
        this.startTimer();
        
        // 防止页面滚动
        document.body.style.overflow = 'hidden';
    }

    /**
     * 绑定事件
     */
    bindEvents() {
        const agreeBtn = document.getElementById('agreeBtn');
        const disagreeBtn = document.getElementById('disagreeBtn');
        
        agreeBtn.addEventListener('click', () => this.handleAgree());
        disagreeBtn.addEventListener('click', () => this.handleDisagree());
        
        // 阻止点击弹窗外区域关闭
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                // 可以选择不允许点击外部关闭，或者调用 handleDisagree
                // this.handleDisagree();
            }
        });
    }

    /**
     * 开始计时器
     */
    startTimer() {
        this.startTime = Date.now();
        const duration = this.agreement.min_read_time * 1000; // 转为毫秒
        
        const updateTimer = () => {
            const elapsed = Date.now() - this.startTime;
            const remaining = Math.max(0, duration - elapsed);
            const remainingSeconds = Math.ceil(remaining / 1000);
            const progress = Math.min(100, (elapsed / duration) * 100);
            
            // 更新显示
            const remainingTimeEl = document.getElementById('remainingTime');
            const progressEl = document.getElementById('timerProgress');
            const agreeBtn = document.getElementById('agreeBtn');
            
            if (remainingTimeEl) {
                remainingTimeEl.textContent = remainingSeconds;
            }
            
            if (progressEl) {
                progressEl.style.width = progress + '%';
            }
            
            if (remaining <= 0) {
                // 时间到，启用同意按钮
                if (agreeBtn) {
                    agreeBtn.disabled = false;
                    agreeBtn.textContent = '我已阅读并同意';
                }
                
                // 更新提示文字
                if (remainingTimeEl && remainingTimeEl.parentElement) {
                    remainingTimeEl.parentElement.textContent = '✅ 阅读时间已满足要求，现在可以选择同意或不同意';
                    remainingTimeEl.parentElement.style.color = '#28a745';
                }
            } else {
                // 继续计时
                setTimeout(updateTimer, 100);
            }
        };
        
        updateTimer();
    }

    /**
     * 处理同意协议
     */
    async handleAgree() {
        const readTime = Math.floor((Date.now() - this.startTime) / 1000);
        
        try {
            const response = await fetch('/api/record_agreement', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    agreement_id: this.agreement.id,
                    read_time: readTime
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                this.isAgreed = true;
                this.hideModal();
                if (this.callback) this.callback(true);
            } else {
                alert(data.message || '记录协议同意失败');
            }
        } catch (error) {
            console.error('记录协议失败:', error);
            alert('网络错误，请重试');
        }
    }

    /**
     * 处理不同意协议
     */
    handleDisagree() {
        this.isAgreed = false;
        this.hideModal();
        if (this.callback) this.callback(false);
    }

    /**
     * 隐藏弹窗
     */
    hideModal() {
        if (this.modal) {
            this.modal.remove();
            this.modal = null;
        }
        
        // 恢复页面滚动
        document.body.style.overflow = '';
    }
}

// 创建全局实例
window.agreementModal = new AgreementModal();
